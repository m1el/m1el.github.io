---
layout: page
title: You are using it wrong
permalink: /coding-sewer-tales/004-you-are-using-it-wrong/
series: coding-sewer-tales
order: 4
---

One day, working on a CRUD, I receive a bug report:

> After moving an item, and then deleting it, the item doesn't get deleted.

Okay, that is odd.  Could it be that we're caching something?
I trace all of the DB calls, and I definitely see three things: `move, delete, get`.
Doing `delete, get` gets the item deleted.  Doing `move` before that prevents deletion.
Great, we have a reproducible bug!

Let's think about this:
I perform the dance with move and delete, then run a clean-state backend.
A freshly started backend, which could not have cached anything, still returns the item, so the flaw is certainly in the DB.
And also the DB responses logged by the backend list the items.
Bulletproof logic, cannot be the backend.

I report the result of my investigation in the JIRA ticket, explain it on a daily standup, and say that we need to contact the developers of the DB.

Two Fridays later, on a bi-weekly checkup with my manager:

"I noticed you have a bug assigned to you.  It's been three weeks, have you had any progress?"
"I've investigated it, I have explained that I cannot fix it, it is out of our control.  The issue is in the DB, and we need to contact the DB developers."
"I'll keep that concern in mind."  
"OK, and I'll send you an email with the summary of what we have so far."  

Two months later:

"Hey Igor.  There's this bug assigned to you, and it's been open for almost three months.  It's not a good look for your performance.  We need it fixed."  
"We've had this conversation six times.  The JIRA ticket has a clear explanation why it's a DB problem, why we should contact the DB developers, and why this is out of our control.  I explained this on the daily three times on your request.
Here's an email from two months ago with an overview.  Here's a Skype message from a month ago with a link to the JIRA ticket, comment excerpts, and a summary of the situation."  
"Fine, we'll contact the DB developers."  

Next week: "Hey Igor, so the DB developers told me it's not a DB problem, and they're very good professionals.  They told me you're using the REST API wrong."  
"Idk what to tell you.  I am certain that I cannot fix it here, it doesn't logically make sense.  We talked about this."  
"OK, so here's what we're going to do.  I'm going to give you access to the JIRA for the DB, and you're going to make a ticket.  But it needs to be a very good bug report, because the DB developers are busy."  
"It is going to be the very best bug report."  
"Oh, and you can't use the REST API, you need to use only the official vendor tools."  
"Sure, let's get this over with."  

After poking around with the vendor CLI tools, there's a bit of a roadblock.
Reading the man page didn't help, so I contacted N, one of the people working on the C++ codebase.

"Hey, N.  I am trying to use the vendor CLI tool to make some queries to the DB.
The CLI tells me that it needs a secondary GUID to fetch items.
First of all, what is a secondary GUID?
Isn't the point of a GUID to Globally IDentify an object, Uniquely?"  
"Our system can only list the objects if you give two GUIDs of the parent.  It's for some stupid legacy reason."  
"And how do I provide the secondary GUID to the CLI?"  
"RTFM."  
"I *did* read the manual, cover to cover, there's no mention of a secondary GUID."   
"Oh yeah, there are secret command line options."  
"The fuck do you *mean* 'secret command line options'?!  Secret from **WHO**?!
I have access to the source code, I will [*make it*][you-cant] sing its man page in soprano if I want to!"  
"Access to the source code is not going to be very useful, unless you're really good with C++ *and* have experience with the codebase."  
"We'll see about that."  

So I start digging into the source code, looking for the 'secret options'.

Three days, and I could not find the command line argument parser.
I promise you, I can read code.  I worked on dozens of command line utilities.
Finding the argument parser never took me more than 30 seconds.
On this project, I could barely find the `main` function for the binary.
When I did, the `main` was one statement:

```cpp
int main(int argc, char** argv) {
    return nested::namespace::something<
        lost::namespace::wrapper::something<
            something::something<
                arguments::extend<something>>>>::run(argc, argv);
}
```

The problem was, I couldn't "jump to definition", because `ctags` crashed while indexing, and didn't work at all with how they used namespaces.  `grep` for the names returned an immense amount of garbage, because they were using the exact same names for different purposes all over the place.  Visual Studio ran out of RAM on my machine.

You could claim it was a skill issue.  But this kind of roadblock has never happened to me before or after.  And yes, N was right, access to the source code was not very productive.

But, I wasn't going to give up.  "The strings for command line options are inside this binary.  And I *will* find them."
So I run `strings` on the file, and lo and behold, there are multiple strings looking like `/FOO` and `/BAR`, all bunched together.
Trying them one by one revealed a way to provide the *second* ID.
Needless to say, those options were nowhere to be seen in the manual.
`strings` turned out to be a better `man`.

After a week of intensive S&M sessions with C++, I had the bug report.
It was using exclusively vendored tools, with detailed repro steps,
reproducible 100% of the time,
with a video of me reproducing it three times in a row,
showing all relevant system state on video at all times.
It was the best write-up I've seen on the entire JIRA board.

Impeccable.  Clear.  Undeniable.  Now they have no choice but to admit there is a bug–

7 minutes after the bug report:

> We have unit tests that cover item deletion.  You're using the REST API wrong.
>
> not-a-bug.  Closed.

I was *really* close to snapping and raging in the comments & possibly quitting that day.
Instead, I chose to go to the gym and punch a sandbag for 15 minutes.

Channeling all of my inner Buddha, I respond:

> I'm not merely deleting the item.  I am moving the item, *then* deleting it.
>
> Please see the reproduction steps.

And the response:

> OOOHH, I see!  We have a RefCount problem in our deletion code path.

No apology for dragging their feet for a month after the initial report.
No apology for completely ignoring the bug report I spent a week on.
Just "whoopsie, I'm so silly".

The bugfix eventually propagates through the pipeline.

And I can finally be relieved of bi-weekly lectures on how long it takes me to fix a single bug.

## Lessons learned?

Sometimes you work with <!--complete retards--> very difficult people, and it's not worth your sanity or time.

[you-cant]: https://youtu.be/8Gp-RXCLO2M?t=3903 "Unix commands don't just say 'you can't; it's not a file'"
