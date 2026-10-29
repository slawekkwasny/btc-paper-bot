# Take-Home: Build a Bitcoin Trading Bot

Build a paper-trading bot for Bitcoin, with a strategy of your own, that is profitable over the last 24 hours. Take at most 4 hours. When you send it, we'll rerun it on the latest 24 hours and it must still be profitable.

## The task

Write a bot that replays the last 24 hours of BTC/USD prices and trades them with your strategy, as if it had been running live. No real money: it starts with 10,000 USD of paper money. Any language, any AI tools.

## Rules

- **Profitable:** it ends the 24 hours with more than 10,000 USD, after fees.
- **At least 5 trades:** a trade is a buy and the sell that closes it.
- **Flat at the end:** it holds 0 BTC when the 24 hours end. Everything it buys, it sells inside the window.
- **Fees:** 0.1% on every buy and every sell.
- **Long only:** no leverage, no shorting.
- **No look-ahead:** each decision uses only prices up to that moment.
- **Real data:** the bot fetches prices itself from a free public feed (for example Binance or Coinbase public candles), with no API keys. Candle size is your choice.
- **Rerunnable:** one command, no edits between runs. The window is always the 24 hours before the moment it runs.
- **Time box:** 4 hours of hands-on time.

## What the bot prints

- Every trade: buy time and price, sell time and price, size, fees, profit or loss.
- Totals: number of trades, final balance, profit in USD and %, and buy-and-hold over the same 24 hours for comparison.

## What to send back

Within 3 days:

1. **Repo link** with the full commit history.
2. **A way for us to run it**, either:
   - a hosted link where we press one button and see the results for the latest 24 hours, or
   - setup steps plus one command that work on a clean Mac from a fresh clone. Test this yourself, and name any prerequisites (e.g. Python 3.12, Node 20 or Docker).
3. **A short README:**
   - the strategy in a few sentences: when it buys, when it sells, and why
   - how you came up with it, and what you tried that didn't work
   - the output of your own run, with its date and time
   - which AI tools you used
4. **A 5-minute Loom** explaining the strategy: the core idea, how you got to it, and why you expect it to keep working.

## How we'll judge it

1. **The rerun:** we run it as-is on the latest 24 hours. It must be profitable after fees, make at least 5 trades and end flat.
2. **The strategy:** from your README and Loom, a clear core idea, how you got to it, and why it should work beyond the day you tested it.

## If you think it can't be done

If you conclude the task isn't possible as set, say so. Still send what you built, and explain why in the README and the Loom, with the evidence from what you tried.
