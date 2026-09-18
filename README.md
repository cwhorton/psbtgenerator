# PSBT Generator (Bitcoin SHA256d / BLAKE2b fork)

A single-page tool that builds an **unsigned PSBT** from a few typed values, fills in
everything else from a public block explorer, and produces a file that Sparrow Wallet
(or its BLAKE2b build) opens, signs and broadcasts. Each PSBT is deliberately valid on
**only one** of the two chains that split at block 961,640.

## Files

| File | Purpose |
|------|---------|
| `index.html` | The whole app. No build step, no dependencies. |
| `serve.py` | Optional. Serves `index.html` on localhost and proxies explorer requests, for explorers that block direct browser requests (CORS). Standard library only. |

## Running it

**No install at all:** the page is hosted from this repository by GitHub Pages at

<https://cwhorton.github.io/psbtgenerator/>

Open that URL and use it as is. It works with any explorer that allows browser
requests (CORS), which includes `mempool.space` for Bitcoin and
`mempool.kilombino.com` for the BLAKE2b chain. If you do not want to depend on a
mempool instance that lacks CORS support, such as `mempool.guide`, this is the
simplest option: no Python, no local server.

Otherwise, either open `index.html` directly in a browser, or run:

```bash
python3 serve.py
```

and open <http://127.0.0.1:8765/>. Use `serve.py` when the page reports that an
explorer blocks browser requests. At the time of writing that is the case for
`mempool.guide`, whose transaction endpoints lack CORS headers, so the BLAKE2b
default only works through `serve.py` (or by switching to `mempool.kilombino.com`
with the chip under the explorer field).

## Inputs

| Field | Validation | Filled from the explorer |
|-------|------------|--------------------------|
| Input UTXO(s) | `txid:vout`, 64 hex chars, colon, output number. One or more. | Value, script type, address, confirmation, spent status, raw previous transaction. |
| Destination address | Mainnet `1…`, `3…`, `bc1q…`, `bc1p…`. Checksums verified. | – |
| Amount | Whole satoshis, above the dust limit, covered by the inputs. | – |
| Change address | Same as destination. | – |
| Sats per vByte | Number ≥ 1. | Defaults to the explorer's **Low Priority** rate (`hourFee`). |
| Blake2B | 0 or 1. | Selects the chain, the explorer, and the replay-protection method. |

Every field re-validates as you type and can be edited at any time. The summary and
the Generate button update live.

Supported input types: P2WPKH (`bc1q…`, 20-byte program), P2TR (`bc1p…`) and legacy
P2PKH (`1…`). Other input types are rejected because the PSBT would need scripts the
explorer cannot supply.

## What each mode does to the transaction

**Blake2B = 0 (Bitcoin, SHA256d only).** Explorer `mempool.space`. The transaction gets
an extra `OP_RETURN` output with an 84-byte payload. The whole script is 87 bytes
(`OP_RETURN OP_PUSHDATA1 0x54 <84 bytes>`). The BLAKE2b chain runs BIP-110 (Reduced
Data Temporary Softfork) as a flag-day rule from block 961,640, which makes any
`OP_RETURN` script over 83 bytes consensus-invalid, so this transaction can never be
replayed there. On Bitcoin Core 30+ the output is standard. It costs about 96 vB of
extra fee. The PSBT carries no sighash field, so Sparrow signs with its normal
`SIGHASH_ALL`.

**Blake2B = 1 (BLAKE2b chain only).** Explorer `mempool.guide`. Every input carries
`PSBT_IN_SIGHASH_TYPE = 0x21`, which is `ALL | UNIFIED` (the opt-in unified sighash
from Bitcoin Knots PR 357 / BKIP-0001). The BLAKE2b Sparrow build honours the declared
sighash and signs the unified message. Those signatures do not verify under pre-fork
rules, so the transaction cannot be replayed to SHA256d. Standard Sparrow refuses to
open such a file ("declares unsupported sighash type"), which is intended.

Both modes: transaction version 2, `nLockTime` set to the current tip height of the
selected chain (anti-fee-sniping, as Sparrow does), inputs marked replaceable (RBF),
change dropped into the fee when it would be below dust (a warning is shown).

## What is in the PSBT

BIP-174 version 0. Global map: the unsigned transaction. Per input: the full previous
transaction (`non_witness_utxo`), the spent output (`witness_utxo`, segwit inputs
only), and on the BLAKE2b chain the sighash type. No key derivation data: Sparrow
matches inputs to your wallet by their script, so it signs anything that belongs to the
loaded wallet.

In Sparrow: **File → Open Transaction → From File** (the `.psbt`) or **From Text**
(the base64). Check the inputs and outputs, sign, broadcast.

## Explorer API notes

The page uses the Esplora / mempool API: `/api/tx/{txid}`, `/api/tx/{txid}/hex`,
`/api/tx/{txid}/outspends`, `/api/blocks/tip/height` (falls back to
`/api/v1/blocks/tip/height`) and `/api/v1/fees/recommended` (falls back to
`/api/fee-estimates`). Any compatible explorer can be typed into the explorer field.
The raw previous transaction is hashed locally and checked against the txid, and its
output is compared with the explorer's JSON, so a wrong or tampered response is
rejected.

## Caveats

- Chain-0 safety depends on BIP-110 being enforced on the BLAKE2b chain. In Knots it
  runs from block 961,640 until the parent block's median time reaches 1 September
  2027. After that the OP_RETURN method stops working.
- Chain-1 safety depends on Sparrow signing with `0x21`. The BLAKE2b build shows on the
  transaction screen whether the signatures opt in. If it says they do not, do not
  broadcast.
- Fee sizes are estimates for the supported script types (P2WPKH 68 vB, P2TR 57.5 vB,
  P2PKH 148 vB per input). Sparrow shows the final size after signing.
- `serve.py` binds to `127.0.0.1` only, forwards `GET` requests only, and only to
  `https://<host>/api/...`.
