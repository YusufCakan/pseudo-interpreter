#!/usr/bin/env python3

from .token import *
from .expr import UnaryExpression, BinaryExpression, KeywordExpression, VariableReference
from .code import IfStatement, ForStatement, WhileStatement, PseudoProgram, AssignmentStatement

def skip_eol(ctx):
    token = ctx.peek_token()
    while token == Token('eol', ''):
        ctx.token()
        token = ctx.peek_token()

def pseudo_program(ctx):
    skip_eol(ctx)

    with ctx.ready_context():
        token = ctx.peek_token()
        if token == Token('keyword', 'PROGRAM'):
            ctx.token()

            with ctx.ready_context():
                ident = ctx.token()
                if ident is None or ident.type != 'identifier':
                    raise ParseExpected(ctx, 'program name')

            with ctx.nest():
                skip_eol(ctx)

                with ctx.ready_context():
                    begin_kw = ctx.token()
                    if begin_kw != Token('keyword', 'BEGIN'):
                        raise ParseExpected(ctx, 'BEGIN')

                statements = statement_list(ctx)

            return PseudoProgram(ident.value, statements).assoc(ctx)

        else:
            raise ParseExpected(ctx, 'PROGRAM')

def statement_list(ctx, end_kw='END', consume_end=True):
    if isinstance(end_kw, str):
        end_kw = (end_kw,)

    def check_end():
        skip_eol(ctx)

        token = ctx.peek_token()
        if token == Token('keyword', 'END'):
            if consume_end:
                ctx.token()
                # treat END, END IF, END WHILE equally
                qual = ctx.peek_token()
                if qual.type == 'keyword':
                    ctx.token()

            return True

        elif token.type == 'keyword' and token.value in end_kw:
            if consume_end:
                ctx.token()

            return True

    with ctx.nest():
        statements = []
        while not check_end():
            with ctx.ready_context():
                stmt = statement(ctx)
                if not stmt:
                    raise ParseExpected(ctx, 'statement')

            statements.append(stmt)

    return statements

def statement(ctx):
    skip_eol(ctx)

    res = assignment_stmt(ctx)
    if not res: res = selection(ctx)
    if not res: res = iteration(ctx)
    if not res: res = jump(ctx)
    if not res: res = io_statement(ctx)

    with ctx.ready_context():
        eol = ctx.token()
        if eol != Token('eol', ''):
            raise ParseExpected(ctx, 'end of statement')
        else:
            pass
            #print("A statement has been born: {}".format(
            #    type(res).__name__
            #))

    return res

def selection(ctx):
    if_kw = ctx.peek_token()
    if if_kw == Token('keyword', 'IF'):
        ctx.token()

        with ctx.ready_context():
            cond = conditional_expr(ctx)
            if not cond:
                raise ParseExpected(ctx, 'conditional')

        then_kw = ctx.peek_token()
        if then_kw.type == 'keyword' and then_kw.value in ('THEN', 'DO'):
            ctx.token() # consume peek

        stmt_list = statement_list(ctx, end_kw=('ELSE', 'END'), consume_end=False)
        else_list = []

        else_kw = ctx.peek_token()
        if else_kw == Token('keyword', 'ELSE'):
            ctx.token() # consume peek
            else_list = statement_list(ctx)

        elif else_kw == Token('keyword', 'END'):
            ctx.token() # consume END peek
            if ctx.peek_token() == Token('keyword', 'IF'):
                ctx.token() # consume END IF keep

        return IfStatement(cond, stmt_list, else_list).assoc(ctx)

def iteration(ctx):
    iter_kw = ctx.peek_token()
    if iter_kw == Token('keyword', 'WHILE'):
        ctx.token() # consume peek

        with ctx.ready_context():
            while_cond = conditional_expr(ctx)
            if not while_cond:
                raise ParseExpected(ctx, 'conditional')

        then_kw = ctx.peek_token()
        if then_kw.type == 'keyword' and then_kw.value in ('THEN', 'DO'):
            ctx.token()

        stmt_list = statement_list(ctx, end_kw='REPEAT')

        return WhileStatement(while_cond, stmt_list).assoc(ctx)

    elif iter_kw == Token('keyword', 'FOR'):
        ctx.token() # consume peek

        with ctx.ready_context():
            start_expr = assignment_stmt(ctx)
            if not start_expr:
                raise ParseExpected(ctx, 'assignment')

        with ctx.ready_context():
            to_kw = ctx.token()
            if to_kw != Token('keyword', 'TO'):
                raise ParseExpected(ctx, 'TO')

        with ctx.ready_context():
            end_expr = conditional_expr(ctx)
            if not end_expr:
                raise ParseExpected(ctx, 'expression')

        then_kw = ctx.peek_token()
        if then_kw.type == 'keyword' and then_kw.value in ('THEN', 'DO'):
            ctx.token()

        stmt_list = statement_list(ctx, end_kw='NEXT')

        return ForStatement(start_expr, end_expr, stmt_list).assoc(ctx)

def jump(ctx):
    jump_kw = ctx.peek_token()

def io_statement(ctx):
    io_kw = ctx.peek_token()
    if io_kw == Token('keyword', 'INPUT'):
        ctx.token()

        with ctx.ready_context():
            ref = expression(ctx)
            if not isinstance(ref, VariableReference):
                raise ParseExpected(ctx, 'variable reference')

        return KeywordExpression(io_kw, ref).assoc(ctx)

    elif io_kw.type == 'keyword' and io_kw.value in ('OUTPUT', 'PRINT'):
        ctx.token()

        with ctx.ready_context():
            expr = expression(ctx)
            if not expr:
                raise ParseExpected(ctx, 'expression')

        return KeywordExpression(io_kw, expr).assoc(ctx)

def assignment_stmt(ctx):
    target = ctx.peek_token()
    if target.type == 'identifier':
        ctx.token()

        target = VariableReference(target.value).assoc(ctx)

        with ctx.ready_context():
            op = ctx.token()
            if op.type != 'operator' or op.value not in ('=', '<-', ':='):
                raise ParseExpected(ctx, 'assignment operator', op)

        with ctx.ready_context():
            inner = expression(ctx)
            if not inner:
                raise ParseExpected(ctx, 'expression')

        return AssignmentStatement(target, inner).assoc(ctx)

def expression(ctx):
    return conditional_expr(ctx)

def conditional_expr(ctx):
    res = or_expr(ctx)
    if res: return res

    raise ParseExpected(ctx, 'conditional')

def unary_expr(ctx):
    op = ctx.peek_token()
    if op.type != 'operator' or op.value not in UNARY_OPERATORS:
        return primary_expr(ctx)
    ctx.token()

    with ctx.ready_context():
        arg = unary_expr(ctx)
        if not arg:
            raise ParseExpected(ctx, 'expression')

    return UnaryExpression(op, arg).assoc(ctx)

def primary_expr(ctx):
    with ctx.ready_context():
        res = ctx.token()
        #print("Got primary token: {}".format(res))
        if res.type in ('number', 'string'):
            return res

        elif res.type == 'identifier':
            return VariableReference(res.value).assoc(ctx)

        elif res != Token('symbol', '('):
            raise ParseExpected(ctx, 'expression', res)

    res = expression(ctx)

    with ctx.ready_context():
        end_bracket = ctx.token()
        if end_bracket != Token('symbol', ')'):
            raise ParseExpected(ctx, "')'", end_bracket)

    return res

def _binary_expr(ops, _next_expr):
    def _curr_expr(ctx):
        with ctx.ready_context():
            arg1 = _next_expr(ctx)
            if not arg1:
                raise ParseExpected(ctx, 'expression')

        op = ctx.peek_token()
        #print("Peeked bexpr: {}".format(op))
        if op.value not in ops or op.type not in ('identifier', 'keyword', 'operator'):
            return arg1
        ctx.token()

        with ctx.ready_context():
            arg2 = _curr_expr(ctx)
            if not arg2:
                raise ParseExpected(ctx, 'expression')

        return BinaryExpression(op, arg1, arg2).assoc(ctx)

    return _curr_expr

multiply_expr   = _binary_expr((MUL_OPERATORS + DIV_OPERATORS), unary_expr)
add_expr        = _binary_expr((ADD_OPERATORS + SUB_OPERATORS), multiply_expr)
relation_expr   = _binary_expr((LT_OPERATORS + GT_OPERATORS + LE_OPERATORS + GE_OPERATORS), add_expr)
eq_expr         = _binary_expr((EQ_OPERATORS + NEQ_OPERATORS), relation_expr)
binary_and_expr = _binary_expr(BINARY_AND_OPERATORS, eq_expr)
binary_xor_expr = _binary_expr(BINARY_XOR_OPERATORS, binary_and_expr)
binary_or_expr  = _binary_expr(BINARY_OR_OPERATORS, binary_xor_expr)
and_expr        = _binary_expr(AND_OPERATORS, binary_or_expr)
or_expr         = _binary_expr(OR_OPERATORS, and_expr)