---
layout: post
permalink: /smallest-lambda-eval/
title: The smallest lambda interpreter in JavaScript
date: 2018-01-25 00:21
---

This post is heavily inspired by
[Tom Stuart: Programming with noting][1],
[William Byrd on "The Most Beautiful Program Ever Written"][2],
[Guowei LV -- The Most Beautiful Program Ever Written][3].

When I first learned about [Lambda calculus][4], I was amazed by a strong mathematical basis for anonymous functions used in many languages.

Then I wondered: what's the simplest way to represent lambda functions as data?

<!-- more -->

## Representation

Lambda expressions, such as `λa.λb.(a b)` have three parts: Variables `a`, `b`, Application `(a b)` and Abstraction (or creating a function) `(λa.a)`.

The question of representing code as data would be incomplete without mentioning LISP, where code *is* data that can be transformed.
[The Most Beautiful Program Ever Written][3] dives into that topic, and into the question of evaluation.

All of the features in lambda expressions are available in LISP and have a straightforward representation.
However, LISP AST has quite complex data structures: symbols, strings, linked lists... we need to go simpler.

First, let's use [De Bruijn indices][5] -- instead of variable symbols.
Replace variable names with the number of the nested lambda's argument you want to look up.
For example, an implementation of the K combinator `λa.λb.a` becomes `λλ2`, where 2 means "the argument of the second lambda, going up from this position".

Second, note that the lambda notation has a binary operation -- function application, and a single argument syntax for creating a lambda, the argument being lambda body.

Let's use the following representation:

- variable lookup is a positive integer number which represents a De Bruijn index.
- creating a function is a tuple of zero and function body. `λa.a` becomes `[0, 1]` in JS notation.
- function application is a tuple of two values. `λa.λb.(a b)` becomes `[0, [0, [2, 1]]]`.

## Environment

Since variable are represented as indicies, the most straightforward way to represent environment as linked lists. Or a JS tuple `[head, tail]`.

Why not a stack or an array?  Because multiple scopes could reference the same parent scope, with possibly changing values.

Constructing an environment becomes as simple as constructing a tuple `[currentValue, parentEnv]`.

## Evaluation

It's easy to construct a simple evaluator once you've seen one:

```javascript
function Eval(prog, env) {
    if (typeof prog === 'number') {
        // lookup a variable
        while(--prog) { env = env[1]; }
        return env[0];
    } else if (prog[0] === 0) {
        // constructing a new lambda
        return (arg) => Eval(prog[1], [arg, env]);
    } else {
        // function application
        return Eval(prog[0], env)(Eval(prog[1], env));
    }
}
```

The code mangled to 140 characters or less, for no particular [reason](https://twitter.com/):

```javascript
Eval = function E(p, e) {
 if (typeof p=='number'){while(--p){e=e[1]}return e[0]}
 return p[0]==0?(a)=>E(p[1],[a,e]):E(p[0],e)(E(p[1],e))
}
```

And of course, translated to Common LISP for completeness:

```racket
(defun Eval (prog env)
 (cond
  ((numberp prog)     (nth (1- prog) env))
  ((zerop (car prog)) (lambda (arg) (Eval (cdr prog) (cons arg env))))
  ('t                 (apply (Eval (car prog)) (Eval (cdr prog))))))
```

*note: this code is using cons pairs instead of linked lists to represent the binary tree*

## Does it work?

Let's test this representation and evaluation with simple combinators:

**I combinator** or *identity*: `λx.x`. Trivially translates to `[0, 1]`.

```javascript
var I = Eval([0, 1]);

console.assert(I("test") === "test");
```

**K combinator** or first of two arguments: `λx.λy.x`. Translates to `[0, [0, 2]]`.

```javascript
var K = Eval([0, [0, 2]]);

console.assert(K("first")("second") === "first");
```

**S combinator** or *generalized application*: `λx.λy.λz.((x z) (y z))`. Translates to `[0, [0, [0, [[3, 1], [2, 1]]]]]`.

```javascript
var K = Eval([0, [0, 2]]);
var S = Eval([0, [0, [0, [[3, 1], [2, 1]]]]]);

console.assert(S(K)(K)("test") === "test");
```

**ι combinator**, [Iota combinator][6] or *universal iota combinator*:

`λf.((f S) K)` => `[0, [[1, S], K]]`

Or, expanded: `[0, [[1, [0, [0, [0, [[3, 1], [2, 1]]]]]], [0, [0, 2]]]]`

```javascript
var iota = Eval([0, [[1, [0, [0, [0, [[3, 1], [2, 1]]]]]], [0, [0, 2]]]]);
var iota_I = iota(iota);
var iota_K = iota(iota(iota(iota)));
var iota_S = iota(iota(iota(iota(iota))));

console.assert(iota_I("test") === "test");
console.assert(iota_K("first")("second") === "first");
console.assert(iota_S(iota_K)(iota_K)("test") === "test");
```

## FizzBuzz

Once the interpreter is working, we can run some more [ambitious programs][1].

Using some trivial transformations, Tom Stuart's FizzBuzz becomes the following:

<!-- Precise details of how this program was transformed are lost in time, but it wouldn't be hard to repeat those. -->

```javascript
var Eval = function E(p, e) {
 if (typeof p=='number'){while(--p){e=e[1]}return e[0]}
 return p[0]==0?(a)=>E(p[1],[a,e]):E(p[0],e)(E(p[1],e))
};

ZERO = [0,[0,1]];
ONE = [0,[0,[2,1]]];
TWO = [0,[0,[2,[2,1]]]];
THREE = [0,[0,[2,[2,[2,1]]]]];
FOUR = [0,[0,[2,[2,[2,[2,1]]]]]];
FIVE = [0,[0,[2,[2,[2,[2,[2,1]]]]]]];

INC = [0,[0,[0,[2,[[3,2],1]]]]];
DEC = [0,[0,[0,[[[3,[0,[0,[1,[2,4]]]]],[0,2]],[0,1]]]]];

PLUS = [0,[0,[0,[0,[[4,2],[[3,2],1]]]]]];
MINUS = [0,[0,[[1,DEC],2]]];

MUL = [0,[0,[0,[2,[3,1]]]]];
POW = [0,[0,[2,1]]];

NINE = [[PLUS,FIVE],FOUR];
TEN = [[MUL,TWO],FIVE];
FIFTEEN = [[MUL,FIVE],THREE];
HUNDRED = [[MUL,[[MUL,FIVE],FIVE]],FOUR];

TRUE  = [0,[0,2]];
FALSE = [0,[0,1]];

IF = [0,[0,[0,[[3,2],1]]]];

IS_ZERO = [0,[[1,[0,FALSE]],TRUE]];
LEQ = [0,[0,[IS_ZERO,[[MINUS,2],1]]]];

PAIR = [0,[0,[0,[[1,3],2]]]];
LEFT  = [0,[1,[0,[0,2]]]];
RIGHT = [0,[1,[0,[0,1]]]];
EMPTY = [[PAIR,TRUE],TRUE];
UNSHIFT = [0,[0,[[PAIR,FALSE],[[PAIR,1],2]]]];
IS_EMPTY = LEFT;
FIRST = [0,[LEFT,[RIGHT,1]]];
REST = [0,[RIGHT,[RIGHT,1]]];

Z = [0,[[0,[2,[0,[[2,2],1]]]],[0,[2,[0,[[2,2],1]]]]]];

MOD = [Z,[0,[0,[0,[[[[LEQ,1],2],[0,[[[4,[[MINUS,3],2]],2],1]]],2]]]]];
DIV = [Z,[0,[0,[0,[[[[LEQ,1],2],[0,[[INC,[[4,[[MINUS,3],2]],2]],1]]],ZERO]]]]];
RANGE = [Z,[0,[0,[0,[[[[LEQ,2],1],[0,[[[UNSHIFT,[[4,[INC,3]],2]],3],1]]],EMPTY]]]]];
FOLD = [Z,[0,[0,[0,[0,[[[IS_EMPTY,3],2],[0,[[[2,[[[5,[REST,4]],3],2]],[FIRST,4]],1]]]]]]]];
MAP = [0,[0,[[[FOLD,2],EMPTY],[0,[0,[[UNSHIFT,2],[3,1]]]]]]];
PUSH = [0,[0,[[[FOLD,2],[[UNSHIFT,EMPTY],1]],UNSHIFT]]];
TO_DIGITS = [Z,[0,[0,[[PUSH,[[[[LEQ,1],NINE],EMPTY],[0,[[3,[[DIV,2],TEN]],1]]]],[[MOD,1],TEN]]]]];

B   = TEN;
F   = [INC,B];
I   = [INC,F];
U   = [INC,I];
ZED = [INC,U];
FIZZ = [[UNSHIFT,[[UNSHIFT,[[UNSHIFT,[[UNSHIFT,EMPTY],ZED]],ZED]],I]],F];
BUZZ = [[UNSHIFT,[[UNSHIFT,[[UNSHIFT,[[UNSHIFT,EMPTY],ZED]],ZED]],U]],B];
FIZZBUZZ = [[UNSHIFT,[[UNSHIFT,[[UNSHIFT,[[UNSHIFT,BUZZ],ZED]],ZED]],I]],F];

RESULT = [[0,[[0,[[MAP,[[RANGE,ONE],HUNDRED]],[0,
  [[[3,[[2,1],FIFTEEN]],
    FIZZBUZZ],
   [[[3,[[2,1],THREE]],
     FIZZ],
    [[[3,[[2,1],FIVE]],
      BUZZ],
     [TO_DIGITS,1]]]]
]]],MOD]],IS_ZERO];

// some helper functions to extract data into a readable form.
// lambda bool to JS bool
var to_bool = (fn) => fn(true)(false);
// church numeral to JS number
var to_int = (fn) => fn(x => x+1)(0);
// linked list to JS array
var to_list = (fn) => {
    var list = [];
    var LEFT  = p => p(x => y => x);
    var RIGHT = p => p(x => y => y);
    var FIRST = l => LEFT(RIGHT(l));
    var REST = l => RIGHT(RIGHT(l));
    while (!to_bool(LEFT(fn)))
    {
        list.push(FIRST(fn));
        fn = REST(fn);
    }
    return list;
};

// transform list of numbers to JS string
var to_string = (fn) => {
  var alpha = '0123456789BFiuz';
  return to_list(fn).map(c=>alpha[to_int(c)]).join('');
};

console.log('full program:', JSON.stringify(RESULT));
to_list(Eval(RESULT)).forEach(row => console.log(to_string(row)));
```

## Utility

N/A

## Downsides

The simplicity of this language and evaluator implies a near-impossibility of providing meaningful error messages.

There's almost no applications for this in the real world except for learning how lambda calculus works.

## Future work

- Translate more lambda expressions into data using this notation.

- Write a parser that can translate lambda expressions into this form.

- Write a lazy evaluator.

- Implement an evaluator without using lambda functions provided by the language.

- Implement an evaluator in a language that doesn't support GC.

- Make a lambda -> x64 compiler.

## Summary

Making a simple evaluator was fun. This is probably *the* simplest evaluator of a kind.

This evaluator shows once again the simplicity and expressiveness of lambda calculus, and how it maps onto programming languages.

[1]: https://codon.com/programming-with-nothing
[2]: https://www.youtube.com/watch?v=OyfBQmvr2Hc
[3]: https://www.lvguowei.me/post/the-most-beautiful-program-ever-written/
[4]: https://en.wikipedia.org/wiki/Lambda_calculus
[5]: https://en.wikipedia.org/wiki/De_Bruijn_index
[6]: https://en.wikipedia.org/wiki/Iota_and_Jot
