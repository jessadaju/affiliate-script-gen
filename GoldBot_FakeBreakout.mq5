//+------------------------------------------------------------------+
//|                                      GoldBot_FakeBreakout.mq5    |
//|                        Automated Gold Trading Bot (No Indicator) |
//|                                   With Fake Breakout Detection   |
//+------------------------------------------------------------------+
#property copyright "Your Name"
#property link      "https://www.example.com"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>

// Input Parameters
input group "=== General Settings ==="
input double LotSize = 0.01;                 // Lot Size (0 for Dynamic)
input int    StopLoss = 300;                 // Stop Loss (points)
input int    TakeProfit = 600;               // Take Profit (points)
input int    Slippage = 3;                   // Max Slippage (points)
input string MagicNumber = "GoldBot2024";    // Magic Number Identifier

input group "=== Risk Management ==="
input double RiskPercent = 1.0;              // Risk % per trade (if LotSize=0)
input bool   UseTrailingStop = true;         // Enable Trailing Stop
input int    TrailingStart = 200;            // Trailing Start (points)
input int    TrailingStep = 50;              // Trailing Step (points)
input int    MaxTradesPerDay = 5;            // Max trades per day (0 = unlimited)

input group "=== Fake Breakout Detection ==="
input bool   DetectFakeBreakout = true;      // Enable Fake Breakout Filter
input int    ConfirmationBars = 2;           // Bars to confirm breakout
input double BreakoutThreshold = 0.3;        // Wick ratio threshold (0.3 = 30%)
input int    FakeBreakoutLookback = 10;      // Lookback bars for fake detection

input group "=== Trading Hours ==="
input bool   UseTimeFilter = false;          // Enable Time Filter
input int    StartHour = 8;                  // Start Hour (Server Time)
input int    EndHour = 20;                   // End Hour (Server Time)
input int    StartMinute = 0;                // Start Minute
input int    EndMinute = 0;                  // End Minute

// Global Variables
CTrade trade;
int tradesToday = 0;
datetime lastTradeDate = 0;
string commentPrefix = "GB24: ";

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(StringToInteger(MagicNumber));
   trade.SetDeviationInPoints(Slippage);
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   trade.SetAsyncMode(false);
   
   Print(commentPrefix, "Gold Bot with Fake Breakout Detection Initialized");
   Print(commentPrefix, "Symbol: ", _Symbol, " | Period: ", EnumToString(_Period));
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print(commentPrefix, "Bot Deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check if trading is allowed
   if(!IsTradingAllowed())
      return;
   
   // Reset daily trade counter
   CheckNewDay();
   
   // Check max trades per day
   if(MaxTradesPerDay > 0 && tradesToday >= MaxTradesPerDay)
      return;
   
   // Check time filter
   if(UseTimeFilter && !IsWithinTradingHours())
      return;
   
   // Manage existing positions (Trailing Stop)
   ManagePositions();
   
   // Check if we already have a position
   if(PositionSelect(_Symbol))
      return;
   
   // Generate trading signal
   int signal = GenerateSignal();
   
   if(signal == 1) // Buy Signal
   {
      OpenBuy();
   }
   else if(signal == -1) // Sell Signal
   {
      OpenSell();
   }
}

//+------------------------------------------------------------------+
//| Check if trading is allowed                                        |
//+------------------------------------------------------------------+
bool IsTradingAllowed()
{
   // Check if symbol is tradable
   long tradeAllowed = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(tradeAllowed != SYMBOL_TRADE_MODE_FULL && tradeAllowed != SYMBOL_TRADE_MODE_LONG && tradeAllowed != SYMBOL_TRADE_MODE_SHORT)
   {
      Print(commentPrefix, "Trading not allowed for this symbol");
      return false;
   }
   
   // Check AutoTrading button
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      Print(commentPrefix, "AutoTrading is disabled in terminal");
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Check if new day started                                           |
//+------------------------------------------------------------------+
void CheckNewDay()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   datetime today = StructToTime(dt);
   
   // Reset date at midnight
   if(lastTradeDate != today)
   {
      tradesToday = 0;
      lastTradeDate = today;
      Print(commentPrefix, "New trading day started. Trades reset.");
   }
}

//+------------------------------------------------------------------+
//| Check if current time is within trading hours                      |
//+------------------------------------------------------------------+
bool IsWithinTradingHours()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   
   int currentMinutes = dt.hour * 60 + dt.min;
   int startMinutes = StartHour * 60 + StartMinute;
   int endMinutes = EndHour * 60 + EndMinute;
   
   if(startMinutes <= endMinutes)
   {
      return (currentMinutes >= startMinutes && currentMinutes <= endMinutes);
   }
   else
   {
      // Handles overnight sessions (e.g., 22:00 to 06:00)
      return (currentMinutes >= startMinutes || currentMinutes <= endMinutes);
   }
}

//+------------------------------------------------------------------+
//| Generate trading signal                                            |
//+------------------------------------------------------------------+
int GenerateSignal()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   
   // Get last 20 candles
   int copied = CopyRates(_Symbol, _Period, 0, 20, rates);
   if(copied < 20)
   {
      Print(commentPrefix, "Error copying rates: ", GetLastError());
      return 0;
   }
   
   // Analyze price action
   double currentClose = rates[0].close;
   double currentOpen = rates[0].open;
   double currentHigh = rates[0].high;
   double currentLow = rates[0].low;
   
   double prevClose = rates[1].close;
   double prevOpen = rates[1].open;
   double prevHigh = rates[1].high;
   double prevLow = rates[1].low;
   
   double prev2Close = rates[2].close;
   
   // Calculate candle body and wicks
   double bodyCurrent = MathAbs(currentClose - currentOpen);
   double upperWickCurrent = currentHigh - MathMax(currentClose, currentOpen);
   double lowerWickCurrent = MathMin(currentClose, currentOpen) - currentLow;
   double rangeCurrent = currentHigh - currentLow;
   
   // Determine trend from previous candles
   bool uptrend = (prevClose > prevOpen) && (prevClose > prev2Close);
   bool downtrend = (prevClose < prevOpen) && (prevClose < prev2Close);
   
   // Check for fake breakout patterns
   if(DetectFakeBreakout)
   {
      // Check for potential fake breakout scenarios
      if(IsFakeBreakout(rates, 1)) // Check current bar
      {
         Print(commentPrefix, "Fake breakout detected on current bar - Skipping trade");
         return 0;
      }
      
      if(!ConfirmBreakout(rates))
      {
         Print(commentPrefix, "Breakout not confirmed - Waiting for more bars");
         return 0;
      }
   }
   
   // Buy Signal: Uptrend + Strong bullish candle + No fake breakout
   if(uptrend && 
      bodyCurrent > (rangeCurrent * 0.5) && 
      currentClose > prevHigh &&
      lowerWickCurrent < (rangeCurrent * 0.3))
   {
      Print(commentPrefix, "Buy signal generated");
      return 1;
   }
   
   // Sell Signal: Downtrend + Strong bearish candle + No fake breakout
   if(downtrend && 
      bodyCurrent > (rangeCurrent * 0.5) && 
      currentClose < prevLow &&
      upperWickCurrent < (rangeCurrent * 0.3))
   {
      Print(commentPrefix, "Sell signal generated");
      return -1;
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| Detect fake breakout pattern                                       |
//+------------------------------------------------------------------+
bool IsFakeBreakout(const MqlRates &rates[], int barIndex)
{
   if(barIndex >= ArraySize(rates))
      return false;
   
   double open = rates[barIndex].open;
   double close = rates[barIndex].close;
   double high = rates[barIndex].high;
   double low = rates[barIndex].low;
   
   double body = MathAbs(close - open);
   double upperWick = high - MathMax(close, open);
   double lowerWick = MathMin(close, open) - low;
   double range = high - low;
   
   if(range == 0)
      return false;
   
   // Check for long upper wick (potential fake bullish breakout)
   double upperWickRatio = upperWick / range;
   if(upperWickRatio > BreakoutThreshold && body < (range * 0.3))
   {
      // Additional check: did price break above previous high but close below?
      if(barIndex > 0 && high > rates[barIndex-1].high && close < rates[barIndex-1].high)
      {
         Print(commentPrefix, "Fake bullish breakout detected (long upper wick)");
         return true;
      }
   }
   
   // Check for long lower wick (potential fake bearish breakout)
   double lowerWickRatio = lowerWick / range;
   if(lowerWickRatio > BreakoutThreshold && body < (range * 0.3))
   {
      // Additional check: did price break below previous low but close above?
      if(barIndex > 0 && low < rates[barIndex-1].low && close > rates[barIndex-1].low)
      {
         Print(commentPrefix, "Fake bearish breakout detected (long lower wick)");
         return true;
      }
   }
   
   // Lookback for rejection patterns
   for(int i = 1; i <= FakeBreakoutLookback && (barIndex + i) < ArraySize(rates); i++)
   {
      int checkBar = barIndex + i;
      double checkHigh = rates[checkBar].high;
      double checkLow = rates[checkBar].low;
      double checkClose = rates[checkBar].close;
      double checkOpen = rates[checkBar].open;
      
      // Check if current bar's high was tested but rejected
      if(high > checkHigh && close < checkHigh && (high - close) > (range * BreakoutThreshold))
      {
         Print(commentPrefix, "Rejection pattern detected at resistance");
         return true;
      }
      
      // Check if current bar's low was tested but rejected
      if(low < checkLow && close > checkLow && (close - low) > (range * BreakoutThreshold))
      {
         Print(commentPrefix, "Rejection pattern detected at support");
         return true;
      }
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Confirm breakout validity                                          |
//+------------------------------------------------------------------+
bool ConfirmBreakout(const MqlRates &rates[])
{
   if(ArraySize(rates) < ConfirmationBars + 1)
      return false;
   
   double currentClose = rates[0].close;
   double currentOpen = rates[0].open;
   bool isBullish = currentClose > currentOpen;
   
   // Check previous confirmation bars
   int confirmCount = 0;
   for(int i = 1; i <= ConfirmationBars; i++)
   {
      if(i >= ArraySize(rates))
         break;
         
      double barClose = rates[i].close;
      double barOpen = rates[i].open;
      bool barBullish = barClose > barOpen;
      
      if(isBullish && barBullish)
         confirmCount++;
      else if(!isBullish && !barBullish)
         confirmCount++;
   }
   
   // Require at least 70% of confirmation bars to match direction
   double confirmRatio = (double)confirmCount / ConfirmationBars;
   if(confirmRatio >= 0.7)
   {
      Print(commentPrefix, "Breakout confirmed with ", confirmCount, "/", ConfirmationBars, " bars");
      return true;
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Open Buy Position                                                  |
//+------------------------------------------------------------------+
void OpenBuy()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl = (StopLoss > 0) ? ask - StopLoss * _Point : 0;
   double tp = (TakeProfit > 0) ? ask + TakeProfit * _Point : 0;
   
   double lotSize = CalculateLotSize(ask, sl);
   
   if(lotSize <= 0)
   {
      Print(commentPrefix, "Invalid lot size calculated");
      return;
   }
   
   if(trade.Buy(lotSize, _Symbol, ask, sl, tp, "Buy - Fake Breakout Filter"))
   {
      tradesToday++;
      Print(commentPrefix, "Buy order opened: Lot=", lotSize, " SL=", sl, " TP=", tp);
   }
   else
   {
      Print(commentPrefix, "Buy order failed: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Open Sell Position                                                 |
//+------------------------------------------------------------------+
void OpenSell()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = (StopLoss > 0) ? bid + StopLoss * _Point : 0;
   double tp = (TakeProfit > 0) ? bid - TakeProfit * _Point : 0;
   
   double lotSize = CalculateLotSize(bid, sl);
   
   if(lotSize <= 0)
   {
      Print(commentPrefix, "Invalid lot size calculated");
      return;
   }
   
   if(trade.Sell(lotSize, _Symbol, bid, sl, tp, "Sell - Fake Breakout Filter"))
   {
      tradesToday++;
      Print(commentPrefix, "Sell order opened: Lot=", lotSize, " SL=", sl, " TP=", tp);
   }
   else
   {
      Print(commentPrefix, "Sell order failed: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Calculate dynamic lot size based on risk                           |
//+------------------------------------------------------------------+
double CalculateLotSize(double price, double sl)
{
   if(LotSize > 0)
      return NormalizeDouble(LotSize, 2);
   
   if(sl == 0 || price == 0)
      return 0.01;
   
   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = accountBalance * (RiskPercent / 100.0);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(tickValue == 0 || tickSize == 0)
      return 0.01;
   
   double slDistance = MathAbs(price - sl);
   double lots = riskAmount / (slDistance / tickSize * tickValue);
   
   // Apply broker limits
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lots = MathMax(minLot, MathMin(maxLot, lots));
   lots = NormalizeDouble(MathFloor(lots / lotStep) * lotStep, 2);
   
   return MathMax(minLot, lots);
}

//+------------------------------------------------------------------+
//| Manage existing positions (Trailing Stop)                          |
//+------------------------------------------------------------------+
void ManagePositions()
{
   if(!UseTrailingStop)
      return;
   
   if(!PositionSelect(_Symbol))
      return;
   
   ulong magic = StringToInteger(MagicNumber);
   if(PositionGetInteger(POSITION_MAGIC) != magic)
      return;
   
   double positionOpenPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   double currentSL = PositionGetDouble(POSITION_SL);
   ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   
   double currentPrice = (posType == POSITION_TYPE_BUY) ? 
                         SymbolInfoDouble(_Symbol, SYMBOL_BID) : 
                         SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   
   double profitPoints = (posType == POSITION_TYPE_BUY) ? 
                         (currentPrice - positionOpenPrice) / _Point : 
                         (positionOpenPrice - currentPrice) / _Point;
   
   if(profitPoints < TrailingStart)
      return;
   
   double newSL = 0;
   if(posType == POSITION_TYPE_BUY)
   {
      newSL = currentPrice - TrailingStep * _Point;
      if(newSL > currentSL + _Point)
      {
         if(trade.PositionModify(_Symbol, newSL, PositionGetDouble(POSITION_TP)))
         {
            Print(commentPrefix, "Trailing Stop updated for BUY: New SL=", newSL);
         }
      }
   }
   else // SELL
   {
      newSL = currentPrice + TrailingStep * _Point;
      if(currentSL == 0 || newSL < currentSL - _Point)
      {
         if(trade.PositionModify(_Symbol, newSL, PositionGetDouble(POSITION_TP)))
         {
            Print(commentPrefix, "Trailing Stop updated for SELL: New SL=", newSL);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Convert MqlDateTime to datetime                                    |
//+------------------------------------------------------------------+
datetime DateTimeToTime(const MqlDateTime &dt)
{
   return StructToTime(dt);
}
//+------------------------------------------------------------------+
