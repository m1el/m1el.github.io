---
layout: post
title: The Most Expensive Anti-Pattern
date: 2015-07-22 11:08
---

In this post, I'd like to talk about the most expensive programming anti-pattern I know:

**Manipulating structured data formats using string functions.**

I will be referring to it as "*printf anti-pattern*".

<!-- more -->

# The cost

When I call it "the most expensive" anti-pattern, it is not an empty claim.

I [counted vulnerabilities by type](https://gist.github.com/m1el/44e2500910a0dba31cbc) using data from [cve.mitre.org](https://cve.mitre.org/), and I got this list of top vulnerability types:

```
rexec: 19268
DoS: 14849
xss: 9236
memory: 8212
sqlinj: 6230
privilege: 3321
dirtraversal: 2762
arith: 1260
csrf: 1117
```

*You're free to criticize how I did it and do it better.*

If you look at top entries, you will notice that XSS and SQL injections contribute a noticeable chunk to the list.

I claim that most XSS and SQL injections are caused by printf anti-pattern.

Inserting random strings into HTML is a terrible idea.  Same goes for SQL.

# Examples

Once you know the definition of printf anti-pattern, you will notice that it is *ubiquitous*.

You will find that this anti-pattern is most common in HTML and SQL.
That's why there are so many SQL injections and XSS vulnerabilities.

Here are a few examples:

- Nearly every PHP web-site in existence

```php
<div class="greeting">Hello, <?php echo $username; ?>!</div>
```

- Any example of SQL query generated using string manipulation (see PHP's docs for [`mysql_query`](http://php.net/manual/en/function.mysql-query.php))

```php
$query = sprintf("SELECT firstname, lastname, address, age FROM friends 
    WHERE firstname='%s' AND lastname='%s'",
    mysql_real_escape_string($firstname),
    mysql_real_escape_string($lastname));
```

- Lots of programmers generating dynamic elements in JavaScript using innerHtml-like techniques, [example](http://mrbool.com/how-to-create-an-editable-html-table-with-jquery/27425):

```javascript
var OriginalContent = $(this).text();
$(this).html("<input type='text' value='" + OriginalContent + "' />");
```

- Some poor programmer writing a dynamic web-site in C:

```C
sprintf(buffer, "<tr><td onclick=putpgtl(\"?j=%d&k=%d&v=%d&h=24\")>%s２４時間</td></tr>", ...)
```

- Generating JSON using string formatting: [gist.github.com/varemenos/e95c2e098e657c7688fd](https://gist.github.com/varemenos/e95c2e098e657c7688fd)

```bash
git log --pretty=format:'{ %n  "commit": "%H",%n  "abbreviated_commit": "%h",%n  "tree": "%T",%n  "abbreviated_tree": "%t",%n  "parent": "%P",%n  "abbreviated_parent": "%p",%n  "refs": "%D",%n  "encoding": "%e",%n  "subject": "%s",%n  "sanitized_subject_line": "%f",%n  "body": "%b",%n  "commit_notes": "%N",%n  "verification_flag": "%G?",%n  "signer": "%GS",%n  "signer_key": "%GK",%n  "author": { %n    "name": "%aN",%n    "email": "%aE",%n    "date": "%aD"%n  },%n  "commiter": { %n    "name": "%cN",%n    "email": "%cE",%n    "date": "%cD"%n  }%n},'
```

```bash
# jesus christ why
(curl json) | jq -c '.[] | {value: .value, name: .name}' | sed -e 's/"name":"//g' -e 's/","value"//g' | tr -d '"}' | grep -v ':0' | awk '{FS=":" ; printf "%20s\t\%d\n",$1,$2}' | less
```

- Using `sed` to process XML:

```bash
# http://askubuntu.com/questions/442013/using-sed-to-search-and-replace-text-in-xml-file
sed -i 's#<!--UpdateAccountGUIDs>UpdateAndExit</UpdateAccountGUIDs-->#<UpdateAccountGUIDs>UpdateAndExit</UpdateAccountGUIDs>#' File.XML
# http://askubuntu.com/questions/284983/print-text-between-two-xml-tags
sed -n '/<serverName/,/<\/serverName/p' big_xml_file.xml
```

- [Code generation in ExtJS](https://github.com/probonogeek/extjs/blob/master/src/data/reader/Reader.js#L662):

```javascript
  '<tpl if="hasCustomConvert">',
  '    dest["{name}"] = value === undefined ? __field{#}.convert(__field{#}.defaultValue, record) : __field{#}.convert(value, record);\n',
  ...
// exploited using
// Ext.define('m',{extend:'Ext.data.Model',fields:['id']});
// var store = Ext.create('Ext.data.Store',{model:m});
// store.loadRawData({metaData:{fields:['"+alert(1)+"']}});
```

- mal [defining](https://github.com/kanaka/mal/blob/master/process/guide.md#step6) `load-file` as `eval` on string concatenation

> Define a `load-file` function using mal itself. In your main program call the `rep` function with this string: `"(def! load-file (fn* (f) (eval (read-string (str \"(do \" (slurp f) \")\")))))"`.

# Proper Alternatives

*So if I'm generating HTML using string functions, what should I be doing instead?*

You will see that all proposed solutions have a common theme:
manipulate the underlying data structure and then serialize it.

There is no point where a serialized data structure is modified as a string.

### For HTML

- [hiccup](https://github.com/weavejester/hiccup), [hiccup-examples](https://github.com/yokolet/hiccup-samples)

```clojure
(html [:ul
  (for [x (range 1 4)]
       [:li x])])
(defn index []
  [:div {:id "content"}
   [:h1 {:class "text-success"} "Hello Hiccup"]])
```

- lxml [e-factory](http://lxml.de/tutorial.html#the-e-factory)

```python
html = page = (
  E.html(       # create an Element called "html"
    E.head(
      E.title("This is a sample document")
    ),
    E.body(
      E.h1("Hello!", CLASS("title")),
      E.p("This is a paragraph with ", E.b("bold"), " text in it!"),
      E.p("This is another paragraph, with a", "\n      ",
        E.a("link", href="http://www.python.org"), "."),
      E.p("Here are some reservered characters: <spam&egg>."),
    )
  )
)
```

- Manipulate the DOM, then serialize HTML

A toy example would look something like this:

```python
html = etree.parse('template.html')
name_node = html.xpath('//div[@id="user-name"]')[0]
name_node.text = user.name
print(etree.tostring(html))
```

- Server-side AngularJS or React

- Manipulate the DOM directly

e.g. jQuery:

```javascript
var OriginalContent = $(this).text();
$(this).empty().append($('<input type=text>').val(OriginalContent))
// Bad code. BAD!
// $(this).html("<input type='text' value='" + OriginalContent + "' />");
```

### For JSON

- Use object literals or list comprehensions to make a JSON object, then serialize it
- Generate a JSON object and then serialize it

### For SQL

- Use query placeholders
- Manipulate SQL Abstract Syntax Trees, then emit SQL
- [LINQ to SQL](https://msdn.microsoft.com/en-us/library/bb425822.aspx)

### For XML

- Use a sane serialization format instead (see JSON)
- Manipulate the DOM, then serialize XML
- XSLT would qualify if it was not terrible

### For meta-programming

- Lisp
- Manipulate Abstract Syntax Trees for your language

# The Reason

So how did we get here?

I suspect that it happened because people are lazy.

> — Oh, so we have this markup that we can generate simply using string concatenation?  Yeah, let's just do that.
>
> — But if some string contains `<img/src/onerror=alert(1)>`, it will cause JavaScript code execution!
>
> — Ugh, let's write the `htmlspecialchars` function and every time we put some string into HTML, pass the string through this function...
>
> — But if you write `"<img class=" + htmlspecialchars($_GET['cls']) + " src=dot.gif>"`, you can still inject JavaScript!
>
> — But only an idiot would write that code.
>
> — What should we do if our code emits invalid HTML in the first place, without string substitution?
>
> — Just write it carefully next time.

So here we are, generating HTML using string concatenation.

Of course, if you are being really, *really* careful, you can emit valid HTML and SQL with no injection problems.

But you don't use manual memory management and pointer arithmetics when you generate your web-site, do you?

Why would you walk on a razor's edge if you can program in a safe way?

# Browsers

There is, of course, a funnier side to this story: browsers.

Browser vendors had to tune their parsers for broken HTML because many web-sites gave the browsers invalid HTML.
People chose browsers that were able to process nearly arbitrary chunks of bytes as HTML because these browsers were able to display their favorite web-sites.

Browser vendors had to implement XSS filters, because web-sites are prone to putting raw user requests straight into HTML.
The rationale for XSS filters is simple: if browser vendor *can* prevent 90% of XSS attacks on the user, the user will be happy.

However, these filters simply [*can not*](http://securitee.tk/files/chrome_xss.php?a=%3Cscript%3E%27&b=%27;alert%281%29%3C/script%3E) protect from all XSS attacks.

These two examples are browsers dealing with symptoms of the problem, and not with the problem itself.
The problem is in the head of a programmer who thinks that it is reasonable to generate dynamic HTML using string manipulation.

# Conclusion

The state of HTML as a structured data format is terrible because people started manipulating it as a string from the very beginning.
There are many problems (including, but not limited to: XSS, invalid HTML, browser parsing differences) caused by this mistreating of HTML format.

Maybe, just maybe, if available tools did not encourage people to generate HTML as a string, the web would be a better place.

Maybe, just maybe, if we chose a different serialization format for documents on the web, we would not treat it as a string that can be written using printf.

We would definitely have less vulnerabilities if programmers did not think that constructing structured data formats using string functions is an acceptable idea.
