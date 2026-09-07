# `def decrypt_password(enc):`

Our newly built Web UI is great for listing items, but "Read" is only 25% of "CRUD".  We need to build a "configuration wizard" to add new items to the list.  The configuation wizard is merely a bunch of input fields, with some validation and CSS slapped on top.  We take the values, put them in JSON and send it to the server.  Boom, that's "Create" done, we're halfway there!  Delete?  UI done, integrated, deployed, QA'd in 2 days.  That's three quarters of the wizard complete in a two week sprint!  *Surely* "Update" is going to be easy?

Hi. I'm Igor and this is a story about why I studied cryptography.

To make "Update" in CRUD work, we need two things to work correctly:
GETting the data, and POSTing a new version back.  What's the difficulty?

Turns out, a part of that data is a password.  Normally, you're supposed to hash/PBKDF the passwords.
Passwords are *usually* not supposed to be encrypted, as the title implies.
But these passwords are more like authentication tokens, CI secrets.  At some point, someone will need to get the secrets (e.g. to upload artifacts). There's some control over who can read them in plaintext.

Now here is why it matters: when you GET the configuration data, the password field is encrypted.  If you're not supposed to have access, you can't get it in plaintext.  For example:

```
POST /create-item
{ "login": "foo", "password": "hello world" }
-> { "id": 105 }

GET /item/105
{ "login": "foo", "password": "EUKYcrNW2zCk24gCBvZyMrsFWQ==" }
```

What happens if you need to "Update"?  Well, you need to include the plaintext password in the JSON.

And I've had this conversation:  
– "Can we update only the fields which were changed?  Post a partial update?"  
– "No.  That would be too much change."  
– "Can we at least post the encrypted password back?"  
– "No.  You need to post it in plaintext."  
– "Can you at least accept `the_password_has_not_changed` and decrypt it yourself?  There's literally no security consideration here.  I give you back the string which you gave me."  
– "No."  
– "Can the server at least have a function that decrypts the password, so that we can patch in the password ourselves?"  
– "No, that would make it insecure.  However, I can give you an `encrypt_password` function."  
– "That doesn't help at all!  You're not allowing me to update at all."  
– "We'll need to have a meeting to discuss the security implications."  
– "OK, but until then I'm hard-blocked on this."  

Then I've had a discussion with my manager, on why it's difficult to make "Update" work properly.  Convincing how I'm genuinely blocked on this.  

The password decryption meetings got postponed, rescheduled and discussed.  This was dragging on for a month.  I got bored.  Since the problem involved something called "encryption", I wanted to learn cryptography.  So I went on Coursera and enrolled to "Cryptography I" by Dan Boneh.

An important topic this course talks about is vulnerabilities in the encryption schemas.  So I was wondering -- are the any vulnerabilities in this `encrypt_password` schema?

Let's inspect the outputs and see if there's a pattern.

```
>>> encrypt_password("foo")
"EUKYcrNW2zCqWdc="
hex: 11429872b356db30aed334
>>> encrypt_password("bar")
"EUKYcrNW2zCu0zQ="
hex: 11429872b356db30aa59d7
>>> encrypt_password("far")
"EUKYcrNW2zCqV/8="
hex: 11429872b356db30aa57ff
```

What do we see?

- The length of the ciphertext seems to be `8+len(password)`
- The first 8 bytes in the ciphertext are the same.  They're using constant key and IV?
- The encryption of `"foo"` and `"far"` has the same byte in the ciphertext corresponding to `f`
- The encryption of `"bar"` and `"far"` has different bytes in the cyphertext corresponding to `a` and `r`.

Beause they of constant key and IV, and the fact that the first byte can show us if the prefix is correct means we can recover the password, by guessing one byte at a time.

```python
def decrypt_password(enc):
    cipher = base64.b64decode(enc.encode())
    iv_len = 8
    pw_len = len(cipher) - iv_len
    empty = encrypt_password(b"")
    assert cipher[:iv_len] == base64.b64decode(empty), "IV mismatch"
    password = bytearray(pw_len)
    for pos in range(pw_len):
        for guess in range(256):
            password[pos] = guess
            trial = encrypt_password(password[:pos + 1])
            tr_bytes = base64.b64decode(trial)
            matched = tr_bytes[iv_len + pos] == cipher[iv_len + pos]
            if matched:
                break
        else:
            raise RuntimeError("whoopsie-daisy")
    return bytes(password)
```

![](decrypt-password.gif)

I completed "Cryptography I", cracked the encryption method, and was sitting there in disbelief.
Meanwhile, the coordination to schedule a meeting to discuss how to update the configuration has not even started yet.  Yeah.

After a month and a half, they did provide a `decrypt_password` method.
I've already had all the code necessary to do it, all the tests working, so I just drop-replaced my function with the function they provided. Easy change, "Update" complete.  But...

In three days my lovely QAs drop one of the wildest reports on me.

The configuration page is very slow. For some reason the password field grows to megabytes in size, and then the update just stops working.

The only way this size blowup can happen is exponential growth.
Exponential growth in the password field means we're encrypt->base64 the password multiple times.

Oh no.  I made a booboo somewhere.  I *know* I tested the code.  I covered all of it in e2e tests and I have seen it work.
Must be a JS issue?  It's always a JS issue.  Nope, that part is robust and I tested it to exhaustion.
Must be the server issue?  It's about 4 lines of code, there's literally nowhere to make a mistake.

I spent two days trying to narrow down the source of the issue, and there was literally nowhere for the bug to hide.
Can't use a debugger, because the issue is *rare enough* not to happen under a debugger.
On the third day, I get so pissed I add up to three asserts per line of code.  Asserts for literally every assumption I could possibly come up with.  And eventually I get a hit...

```python
assert encrypt_password(decrypted) == encrypted, "password decryption must round trip"
# AssertionError: password decryption must round trip
```

## WAT

Apparently, a function that takes a constant string and returns a new string, **SOMETIMES** silently fails and returns the input string.
I understand programming is hard, but having a heizenbug in a *pure* `string->string` function requires advanced incompetency.

I cuss aloud, pull the crypto-breaking code and send a PR.

– "You had the solution to the encrypted password issue the whole time?" The QA asked me.  
– "For a while, yes."  
– "Why didn't you say so earlier?"  
– "You have to understand it's a vulnerability.  I can't implement server-side features by exploiting Remote Code Execution. I can't make database requests using SQL Injection.  I can't rely on breaking weak crypto for our code to work.  If I did, I'd have to report those issues as well.  Then you'd have to deal with fixing the bug AND breaking the feature built on top of it.  The reason I pull this solution is because I got pissed at all the wasted time."  

## Lessons learned?

Did I learn anything?  I guess I learned not to roll my own crypto.
I learned that asserts are really helpful.
The assert that helped was truly ridiculous, you wouldn't use it in a regular codebase.

If a function has a pure interface, and doesn't change over time, you should be very sorry if it has intermittent failures.

