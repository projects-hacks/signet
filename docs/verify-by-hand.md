# Verify a Signet document by hand

Everything below runs against a real document with tools that were already on
your machine. No Signet code, no account, no request to a server we operate.

If this page did not work, the product's claim would not survive contact with
anyone who checked it, so the commands are the ones that were actually run
rather than the ones that ought to work.

You need `dig`, `openssl`, and a base32 decoder. On Linux that is `base32 -d`
from coreutils. macOS does not ship one, so the `python3` line below stands in.

## What you are checking

A Signet document prints two things under PROOF OF ORIGIN: the locator, which
says where the key lives, and the mark, which is the payload and the signature
separated by a pipe.

```
S1|amt=15580.00;bic=NWBKGB2L;cls=invoice;cur=USD;iban=GB29NWBK60161331926819;id=INV-2026-0611;iss=northpost.dev;ts=2026-08-27T07:34:38+00:00|T2DLIRTAHQI34RWHKYFXYU6L4WOUF45QY3GO7KXNG5QRGOJSYDQS5Z7FB3NNRABXS5GDQLVK3X4KHEYB2YPEEJIFA4T6T3TZWJ5Z2CA
```

The same string is in the QR code, so you can read it off the page or scan it.
`iss` names the domain that signed. The fields between the pipes are the ones
that decide where money goes, and the signature covers exactly those bytes.

## 1. Get the issuer's key from their own domain

```console
$ dig +short TXT _signet.northpost.dev
"v=SIGNET1; k=ed25519; p=Kqf0GFh29fslh099Tr9ruRvy6qI7ITeKC5KY8Wt0YWI="
```

Nobody but the holder of northpost.dev can put a record there. That is the whole
trust anchor: not a certificate authority, not us, the issuer's own domain.

## 2. Turn it into a key openssl will read

An Ed25519 public key in DER is a fixed twelve byte header followed by the
thirty two key bytes, so the header is prepended rather than parsed.

```console
$ KEY=$(dig +short TXT _signet.northpost.dev | tr -d '"' | sed 's/.*p=//')
$ printf '302a300506032b6570032100' | xxd -r -p > pub.der
$ printf '%s' "$KEY" | base64 -d >> pub.der
$ openssl pkey -pubin -inform DER -in pub.der -out pub.pem
```

## 3. Split the mark into what was signed and the signature

```console
$ MARK='paste the string from the document here'
$ printf '%s' "${MARK#S1|}" | sed 's/|.*//' | tr -d '\n' > payload.txt
$ printf '%s' "$MARK" | sed 's/.*|//' > sig.b32
```

Decode the signature to its sixty four raw bytes:

```console
$ base32 -d sig.b32 > sig.bin                        # Linux
$ python3 -c "import base64,sys;p=open('sig.b32').read().strip();\
sys.stdout.buffer.write(base64.b32decode(p+'='*(-len(p)%8)))" > sig.bin   # macOS
```

## 4. Check it

```console
$ openssl pkeyutl -verify -pubin -inkey pub.pem -rawin -in payload.txt -sigfile sig.bin
Signature Verified Successfully
```

## 5. Check that it would have caught a change

Alter one digit of the amount and run the same command:

```console
$ sed 's/15580.00/15580.01/' payload.txt > tampered.txt
$ openssl pkeyutl -verify -pubin -inkey pub.pem -rawin -in tampered.txt -sigfile sig.bin
Signature Verification Failure
```

One cent moves and the signature stops verifying. So does one character of the
IBAN.

## What this does and does not tell you

It tells you that northpost.dev signed these fields, and that these fields have
not changed since. That is the question invoice redirection fraud turns on: the
account number on the page is the account number the issuer put there.

It does not tell you that northpost.dev is the company you think it is, that the
work was done, or that the invoice is owed. Signet answers those separately, and
`docs/limits.md` says how far each answer goes.
