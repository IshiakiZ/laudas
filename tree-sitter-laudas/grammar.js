/**
 * Tree-sitter grammar for Laudas.
 *
 * Generates a parser that produces a concrete syntax tree usable for:
 *   - Syntax highlighting (better than TextMate regex)
 *   - Code folding
 *   - Indentation
 *   - Structure-aware editing in VS Code, Neovim, Helix, Emacs, etc.
 *
 * Build:
 *     npm install -g tree-sitter-cli
 *     tree-sitter generate
 *     tree-sitter test
 *
 * The grammar mirrors the slot-based wire format in laudas.py's parse_file:
 * functions are flat sequences of labeled slots, type aliases are records,
 * `use` brings in another file.
 */

module.exports = grammar({
  name: 'laudas',

  extras: $ => [
    /\s+/,
    $.comment,
  ],

  word: $ => $.identifier,

  rules: {
    source_file: $ => repeat(choice(
      $.use_directive,
      $.type_decl,
      $.function_decl,
    )),

    // ---- comments ----
    comment: $ => /;.*/,

    // ---- top-level: use ----
    use_directive: $ => seq('use', $.string),

    // ---- top-level: type alias ----
    type_decl: $ => seq(
      'type',
      $.type_name,
      '{',
      optional(commaSep($.type_field)),
      '}',
    ),

    type_field: $ => seq(
      $.identifier,
      ':',
      $.type_ref,
    ),

    // ---- top-level: function ----
    function_decl: $ => seq(
      'fn', $.identifier,
      repeat($.fn_slot),
      choice($.body, $.extern_slot),
    ),

    fn_slot: $ => choice(
      $.vis_slot,
      $.for_slot,
      $.eff_slot,
      $.in_slot,
      $.out_slot,
      $.ex_slot,
      $.req_slot,
      $.ens_slot,
      $.prose_slot,
    ),

    vis_slot:   $ => seq('vis', $.vis_value),
    for_slot:   $ => seq('for', $.type_name),
    eff_slot:   $ => seq('eff', $.eff_list),
    in_slot:    $ => seq('in', $.identifier, ':', $.type_ref),
    out_slot:   $ => seq('out', $.type_ref),
    ex_slot:    $ => seq('ex', /[^\n]+/),
    req_slot:   $ => seq('req', /[^\n]+/),
    ens_slot:   $ => seq('ens', /[^\n]+/),
    prose_slot: $ => seq('prose', $.string),

    vis_value: $ => choice(
      'appearing',
      'disappearing',
      seq('disappearing', '(', 'version', ':', $.version, ')'),
    ),

    eff_list: $ => commaSep1($.eff_value),
    eff_value: $ => choice('pure', 'io', 'panics', 'nondet', 'fails', 'cache', 'cache_rw', $.identifier),

    body: $ => seq('do', repeat($._stmt), 'end'),
    extern_slot: $ => seq('extern', $.eff_value, $.string, 'end'),

    // ---- statements (in body) ----
    _stmt: $ => choice(
      $.let_stmt,
      $.if_stmt,
      $.return_stmt,
      $.expr_stmt,
    ),

    let_stmt: $ => seq('let', $.identifier, '=', $._expr),
    if_stmt: $ => seq('if', $._expr, '{', repeat($._stmt), '}',
                      optional(seq('else', '{', repeat($._stmt), '}'))),
    return_stmt: $ => seq('return', optional($._expr)),
    expr_stmt: $ => $._expr,

    // ---- expressions ----
    _expr: $ => choice(
      $.lambda,
      $.binary,
      $.unary,
      $.call,
      $.method_call,
      $.field_access,
      $.list_lit,
      $.record_lit,
      $.parenthesized,
      $.string,
      $.number,
      $.boolean,
      $.identifier,
    ),

    lambda: $ => seq(
      choice(
        $.identifier,
        seq('(', commaSep($.identifier), ')'),
      ),
      '->',
      $._expr,
    ),

    binary: $ => choice(
      ...[
        ['||', 1], ['&&', 2],
        ['==', 3], ['!=', 3],
        ['<', 4], ['>', 4], ['<=', 4], ['>=', 4],
        ['+', 5], ['-', 5],
        ['*', 6], ['/', 6], ['%', 6],
        ['iff', 1], ['implies', 1],
      ].map(([op, p]) => prec.left(p, seq($._expr, op, $._expr)))
    ),

    unary: $ => prec(7, seq('-', $._expr)),

    call: $ => seq($.identifier, '(', commaSep($._expr), ')'),

    method_call: $ => prec.left(8, seq($._expr, '.', $.identifier, '(', commaSep($._expr), ')')),

    field_access: $ => prec.left(8, seq($._expr, '.', $.identifier)),

    list_lit: $ => seq('[', commaSep($._expr), ']'),

    record_lit: $ => seq($.type_name, '{', commaSep(seq($.identifier, ':', $._expr)), '}'),

    parenthesized: $ => seq('(', $._expr, ')'),

    // ---- atoms ----
    type_ref: $ => choice(
      $.primitive_type,
      $.refined_type,
      $.generic_type,
      $.option_type,
      $.type_name,
    ),

    primitive_type: $ => choice('int', 'bool', 'str', 'float', 'bytes', 'unit'),
    option_type: $ => seq($.primitive_type, '?'),
    generic_type: $ => seq(choice('list', 'map', 'set', 'option', 'result'), '<', commaSep($.type_ref), '>'),
    refined_type: $ => seq($.primitive_type, '{', /[^}]+/, '}'),

    type_name: $ => /[A-Z][A-Za-z0-9_]*/,

    string: $ => /"([^"\\]|\\.)*"/,
    number: $ => /-?\d+/,
    boolean: $ => choice('true', 'false', 'True', 'False'),
    version: $ => /\d+(\.\d+)*/,

    identifier: $ => /[a-z_][A-Za-z0-9_]*/,
  }
});

function commaSep(rule) {
  return optional(commaSep1(rule));
}

function commaSep1(rule) {
  return seq(rule, repeat(seq(',', rule)));
}
