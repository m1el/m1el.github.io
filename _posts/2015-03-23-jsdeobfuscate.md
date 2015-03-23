---
layout: post
title: Deobfuscating jsobfu
date: 2015-03-23 04:08
---

There was a [post][1] on metasploit blog about improvements to
jsobfu — obfuscator for JavaScript.  I find jsobfu particularly interesting
and that is why I wrote a deobfuscator for it.

<!-- more -->

# Obfuscation in general

The purpose of obfuscating the code is to give everyone reading the code a lot of headache.
For assembly, there are plenty of ways code might be scrambled and made hard to comprehend.
Self-modifying code, using debugging registers, unnecessary jumps, jumping into
the middle of an instruction...  All of these are very useful and hard to deal with.

These methods are not available for JS — the code is not self-modifying,
it's impossible to jump in the middle of an instruction because there are no instructions.
There is of course a very complicated and dymanic runtime enviroment such as browser.

Most JS obfuscators I've seen are using some combination of the following techniques:

- minimize code by removing whitespace
- replace variable names with similar names (Oo08)
- replace property accessors such as `.length` with `['length']`
- put string constants into a global table and accessors now look like `[O0O_8[5+5]]`
- calculate property names before accessing properties
- wrap code into some packer that is going to `eval` the code eventually

Most of these techniques are easily undone:
minimizing is undone by [jsbeautifier][2],
scrambling variable names can be dealt woth by minimizing the code with some minimizer and beautufying the code,
property accessors can be mostly undone by replacing with regexes and tiny bit of logic,
evaluating the code can be caught by replacing the `eval` function with `console.log.bind(console)`.

# The jsobfu case

The [jsobfu][3] is interesting because it replaces string constants with expressions that
evaluate to given string.  One can't deal with that using regexes.
And one probably can't deal with it in a fast way.

For example `"ABC";` might be replaced with `String.fromCharCode(0101,0x42,0x43);` or `(function () { var t="C",_="B",h="A"; return h+_+t })(); `.

Or something like

```javascript
(function(){var k=String.fromCharCode(0103),d=String.fromCharCode(0x42),
  v=(function () { var I="A"; return I })();return v+d+k;})();
```

The plan to reverse jsobfu was to

1. obtain <abbr title="Abstract Syntax tree">AST</abbr> for code
2. fold constant expressions to constants
3. print beautified code for new AST

I achieved (1) and (3) by using [esprima][4] parser and [escodegen][5] code generator.
Which leaves us with the most interesting part.  At this point, I decided to call the project [esdeobfuscate][7]

# Constant folding

Constant folding was achieved by marking expressions as "pure" and replacing constant nodes
with literal representing their value.

For example, code calculating value for binary operations:

```javascript
case 'BinaryExpression':
    left = const_collapse_scoped(astNode.left);
    right = const_collapse_scoped(astNode.right);
    if (left.pure && right.pure && astNode.operator in boperators) {
        return mkliteral(boperators[astNode.operator](left.value, right.value));
    } else {
        return {
            type: astNode.type,
            operator: astNode.operator,
            left: left,
            right: right
        };
    }
```

`astNode` represents the node under question, if left and right children of the node are "pure",
the node is replaced with the value that is calculated by applying binary operator to values from left and right children.

If there was a code `"len" + "gth"`, represented by the following AST:

```javascript
{
  type: 'BinaryExpression',
  operator: '+',
  left:  {type: 'Literal', pure: true, value: 'len'},
  right: {type: 'Literal', pure: true, value: 'gth'}
}
```

It is going to be replaced with:

```javascript
{type: 'Literal', pure: true, value: 'length'}
```

By using pattern matching it is possible to find all occurences of `String.fromCharCode`
and calculate the strings that are represented this way.

The most notable part, of course, is calculating the value of anonymous functions.

This was done by testing if function does not modify anything and does not call any "impure" functions.
All variables are added to scope of the function and "pure" variables are calculated immediately.

If a return value can be calculated from "pure" variables and the rest of the function is "pure",
the function is replaced with the literal representing that value.

# Conclusion

Statically deobfuscating JS code that relies on complex JS behavior was a fun exercise.

There is no way to stop a determined analyst from deobfuscating the code,
and esdeobfuscate is another confirmation of that statement.

This project might be used by JS code analysis tools to reduce noise from dynamic string generation.

The code for esdeobfuscate is available at [github][7] with [live example][8].

P.S. LISP users are probably laughing hard at this problem.

[1]: https://community.rapid7.com/community/metasploit/blog/2014/12/27/improvements-to-jsobfu
[2]: http://jsbeautifier.org/
[3]: https://github.com/rapid7/jsobfu
[4]: http://esprima.org/
[5]: https://github.com/estools/escodegen
[6]: http://www.jsfuck.com/
[7]: https://github.com/m1el/esdeobfuscate
[8]: http://m1el.github.io/esdeobfuscate/
