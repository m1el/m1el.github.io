---
layout: page
title: Standup Code Review
permalink: /coding-sewer-tales/003-standup-code-review/
series: coding-sewer-tales
order: 3
---

A long time ago in a galaxy far away, Google Chrome did not have a monopoly on browsers.  So web developers needed to be careful about supporting different browsers, and work with the lowest common denominator of features.

So we needed a way to tell people the website is not compatible with their browser.

Babel didn't exist, and npm was not an established technology. 
[browserslist][browserslist-init] and [detect-browser][detect-browser-init] did not exist.

The project we're talking about used the Sencha Touch (ExtJS) framework.

How is that relevant?  The JS build process involved using Sencha tools to combine and compact JavaScript.
The framework threw a global exception due to some feature being missing in the old browsers.
That exception is thrown *before* any of the application code runs.

So the browser compatibility check needs to exist outside of the compiled code.

Okay, I write a JS file to detect browser version from `navigator.userAgent`,
using regex matching.  Here's my reconstruction of the code from memory.
There's a reason I include it here, so please at least skim it.

```js
(function(){
var BROWSER_REGEX = [
    ['ie', / MSIE (\d+)\.\d+;/],
    ['chrome', /Chrome\/(\d+)\.\d+/],
    //...more
];
var MIN_VERSION = {ie: 8, chrome: 27, /*...*/};
var good = false;

for (var i = 0; i < BROWSER_REGEX.length; i++) {
    var key = BROWSER_REGEX[i][0];
    var regex = BROWSER_REGEX[i][1];
    var match = navigator.userAgent.match(regex);
    if (!match) { continue; }
    if (+match[1] >= MIN_VERSION[key]) {
        good = true;
        break;
    }
}
if (!good) {
    alert('Unsupported browser, please use Internet Explorer 8+, Opera 12+, Chrome 27+, Firefox 3.6+');
}
})();
```

I test it on every user-agent string I could find. It shows the error on every outdated browser I could run.  Code is pushed for review.  Happy.

Next morning comes, and we have a daily standup with 20 people to report the status.

Me: "I worked on ticket number 4016, showing error messages for unsupported browsers.  Created code review request, pls take a look."  
P (team lead): "That code is utter shit, nobody writes code like that."

The normal reaction to your work being criticized with words that strong in front of 20 people would be shame, outrage, being offended, or anger.

I was bewildered.  I put thought and effort into making this.  I made sure it works.
I made sure it complies with the coding practices put in place.
There's about 30 lines of code.  Each line serves a purpose.  Each line is readable.
Variable names are a bit short but make sense.
I don't know of a way to make it simpler or shorter.
What could possibly be there to elicit such a reaction?

The reason I wasn't offended or ashamed is that I don't self-identify with the code I wrote.
I know it's shit.  The point of code reviews is to make code less shit.
And if you tell me that I'm being retarded and missing an obvious way to make the code better,
as long as you're correct, I don't care about the tone.

Shitting on somebody's work with no substance, in front of 20 people?  That's poor manners *and* a demonstration of incompetence.

(Later that day, DMs)

Me: "You're unhappy with the code.  How do you suggest we implement the browser compat check?"  
P: "The code is not being built by Sencha tools, not a part of the standard pipeline."  
Me: "The commit message explains why we can't do that.  Old browsers would throw an exception before reaching the check."  
P: "I see."

Change accepted with no comments.

Me: how the fuck do you flip from "this code is shit" to "accepted with no comments"???

[browserslist-init]: https://github.com/browserslist/browserslist/commit/ad56a8704eb3824e1d6bc06e5aa782a83e2a0bb1

[detect-browser-init]: https://github.com/DamonOehlman/detect-browser/commit/3ba5d8e860e5a2f3ea6dcc2f6dfa4b9c2f2fb398