//+------------------------------------------------------------------+
//|                                              GoldBot_NoIndicator.mq5 |
//|                                  Automated Gold Trading Bot (No Indicators) |
//|                                           Based on Price Action & Time |
//+------------------------------------------------------------------+
#property copyright "Your Name"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

// Input Parameters
input double LotSize = 0.01;              // Lot size for trades
input int    StopLossPoints = 500;        // Stop Loss in points
input int    TakeProfitPoints = 1000;     // Take Profit in points
input int    MagicNumber = 123456;        // Magic number for order identification
input int    Slippage = 3;                // Maximum slippage in points
input bool   UseTimeFilter = true;        // Enable time-based trading filter
input int    StartHour = 8;               // Trading start hour (server time)
input int    EndHour = 20;                // Trading end hour (server time)
input int    MaxDailyTrades = 5;          // Maximum trades per day
input double RiskPercent = 1.0;           // Risk percentage per trade (if dynamic lot)
input bool   UseDynamicLot = false;       // Use dynamic lot size based on risk

// Fake Breakout Detection Parameters
input bool   DetectFakeBreakout = true;   // Enable fake breakout detection
input int    ConfirmationBars = 2;        // Number of bars to confirm breakout validity
input double BreakoutThreshold = 0.3;     // Minimum body/wick ratio to consider valid breakout
input int    FakeBreakoutLookback = 10;   // Lookback period for detecting previous breakouts

// Global Variables
CTrade trade;
datetime lastTradeDate = 0;
int dailyTradeCount = 0;
double dailyHigh = 0;
double dailyLow = 0;
bool dailyRangeInitialized = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(Slippage);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   
   Print("Gold Bot (No Indicator) initialized successfully.");
   Print("Symbol: ", _Symbol, " | Timeframe: ", EnumToString(_Period));
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("Gold Bot deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check if symbol is valid for trading
   if(!IsSymbolValid()) return;
   
   // Reset daily trade count if new day
   CheckNewDay();
   
   // Initialize daily range
   InitializeDailyRange();
   
   // Update daily high and low
   UpdateDailyRange();
   
   // Check time filter
   if(UseTimeFilter && !IsWithinTradingHours()) return;
   
   // Check maximum daily trades
   if(dailyTradeCount >= MaxDailyTrades)
   {
      Print("Maximum daily trades reached: ", dailyTradeCount);
      return;
   }
   
   // Check if we already have open positions
   if(PositionsTotalForSymbol() > 0)
   {
      // Manage existing positions (trailing stop, etc.)
      ManagePositions();
      return;
   }
   
   // Generate trading signal based on price action (no indicators)
   int signal = GenerateSignal();
   
   if(signal == 1) // Buy signal
   {
      OpenBuyOrder();
   }
   else if(signal == -1) // Sell signal
   {
      OpenSellOrder();
   }
}

//+------------------------------------------------------------------+
//| Check if symbol is valid for trading                             |
//+------------------------------------------------------------------+
bool IsSymbolValid()
{
   if(!SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE))
   {
      Print("Symbol ", _Symbol, " is not available for trading.");
      return false;
   }
   
   if(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_ALLOWED) == false)
   {
      Print("Trading is not allowed for ", _Symbol);
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Check if it's a new day and reset counters                       |
//+------------------------------------------------------------------+
void CheckNewDay()
{
   datetime currentTime = TimeCurrent();
   MqlDateTime currentDateTime;
   TimeToStruct(currentTime, currentDateTime);
   
   datetime todayStart = StructToTime(currentDateTime);
   
   if(lastTradeDate != todayStart)
   {
      lastTradeDate = todayStart;
      dailyTradeCount = 0;
      dailyRangeInitialized = false;
      Print("New day started. Daily trade count reset.");
   }
}

//+------------------------------------------------------------------+
//| Initialize daily range at the start of the day                   |
//+------------------------------------------------------------------+
void InitializeDailyRange()
{
   if(!dailyRangeInitialized)
   {
      dailyHigh = iHigh(_Symbol, PERIOD_D1, 0);
      dailyLow = iLow(_Symbol, PERIOD_D1, 0);
      dailyRangeInitialized = true;
      Print("Daily range initialized - High: ", dailyHigh, " Low: ", dailyLow);
   }
}

//+------------------------------------------------------------------+
//| Update daily high and low                                        |
//+------------------------------------------------------------------+
void UpdateDailyRange()
{
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   if(currentPrice > dailyHigh)
      dailyHigh = currentPrice;
   
   if(currentPrice < dailyLow)
      dailyLow = currentPrice;
}

//+------------------------------------------------------------------+
//| Check if current time is within trading hours                    |
//+------------------------------------------------------------------+
bool IsWithinTradingHours()
{
   MqlDateTime currentTime;
   TimeToStruct(TimeCurrent(), currentTime);
   
   int currentHour = currentTime.hour;
   
   if(currentHour >= StartHour && currentHour < EndHour)
      return true;
   
   return false;
}

//+------------------------------------------------------------------+
//| Count total positions for current symbol                         |
//+------------------------------------------------------------------+
int PositionsTotalForSymbol()
{
   int count = 0;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol && 
            PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         {
            count++;
         }
      }
   }
   
   return count;
}

//+------------------------------------------------------------------+
//| Check for fake breakout pattern                                  |
//+------------------------------------------------------------------+
bool IsFakeBreakout(int signalType)
{
   if(!DetectFakeBreakout)
      return false;
   
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   
   int barsNeeded = ConfirmationBars + FakeBreakoutLookback + 2;
   if(CopyRates(_Symbol, _Period, 0, barsNeeded, rates) < barsNeeded)
      return false;
   
   // Check for previous failed breakouts in the lookback period
   for(int i = 1; i <= FakeBreakoutLookback; i++)
   {
      double barHigh = rates[i].high;
      double barLow = rates[i].low;
      double barClose = rates[i].close;
      double barOpen = rates[i].open;
      double barBody = MathAbs(barClose - barOpen);
      double totalRange = barHigh - barLow;
      
      if(totalRange == 0) continue;
      
      // Calculate upper and lower wicks
      double upperWick = barHigh - MathMax(barClose, barOpen);
      double lowerWick = MathMin(barClose, barOpen) - barLow;
      
      // For buy signal: check if there were failed upside breakouts (long upper wicks)
      if(signalType == 1)
      {
         double wickRatio = upperWick / totalRange;
         if(wickRatio > BreakoutThreshold && barClose < barOpen)
         {
            // Found a failed upside breakout (rejection)
            Print("Fake breakout detected: Failed upside breakout at bar ", i);
            return true;
         }
      }
      // For sell signal: check if there were failed downside breakouts (long lower wicks)
      else if(signalType == -1)
      {
         double wickRatio = lowerWick / totalRange;
         if(wickRatio > BreakoutThreshold && barClose > barOpen)
         {
            // Found a failed downside breakout (rejection)
            Print("Fake breakout detected: Failed downside breakout at bar ", i);
            return true;
         }
      }
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Confirm breakout validity with multiple bars                     |
//+------------------------------------------------------------------+
bool ConfirmBreakout(int signalType)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   
   int barsNeeded = ConfirmationBars + 1;
   if(CopyRates(_Symbol, _Period, 0, barsNeeded, barsNeeded) < barsNeeded)
      return false;
   
   // Check if the breakout is confirmed by subsequent bars
   double breakoutLevel = (signalType == 1) ? rates[1].high : rates[1].low;
   
   for(int i = 0; i < ConfirmationBars; i++)
   {
      if(signalType == 1) // Buy confirmation
      {
         // Price should stay above breakout level
         if(rates[i].low < breakoutLevel)
            return false;
         
         // Prefer bullish or neutral candles
         if(rates[i].close < rates[i].open)
         {
            // If bearish, the body should be small
            double body = rates[i].open - rates[i].close;
            double range = rates[i].high - rates[i].low;
            if(range > 0 && body / range > 0.7)
               return false;
         }
      }
      else if(signalType == -1) // Sell confirmation
      {
         // Price should stay below breakout level
         if(rates[i].high > breakoutLevel)
            return false;
         
         // Prefer bearish or neutral candles
         if(rates[i].close > rates[i].open)
         {
            // If bullish, the body should be small
            double body = rates[i].close - rates[i].open;
            double range = rates[i].high - rates[i].low;
            if(range > 0 && body / range > 0.7)
               return false;
         }
      }
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Generate trading signal based on price action                    |
//+------------------------------------------------------------------+
int GenerateSignal()
{
   // Get current price data
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = ask - bid;
   
   // Get recent price data using copy rates
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   
   if(CopyRates(_Symbol, _Period, 0, 5, rates) < 5)
   {
      Print("Failed to copy rates data");
      return 0;
   }
   
   // Simple price action strategy:
   // Buy if price breaks above previous candle high with momentum
   // Sell if price breaks below previous candle low with momentum
   
   double currentClose = rates[0].close;
   double currentOpen = rates[0].open;
   double currentHigh = rates[0].high;
   double currentLow = rates[0].low;
   
   double prevClose = rates[1].close;
   double prevOpen = rates[1].open;
   double prevHigh = rates[1].high;
   double prevLow = rates[1].low;
   
   double prevPrevClose = rates[2].close;
   
   // Calculate candle body sizes
   double currentBody = MathAbs(currentClose - currentOpen);
   double prevBody = MathAbs(prevClose - prevOpen);
   
   // Calculate wicks for fake breakout detection
   double currentUpperWick = currentHigh - MathMax(currentClose, currentOpen);
   double currentLowerWick = MathMin(currentClose, currentOpen) - currentLow;
   double currentRange = currentHigh - currentLow;
   
   // Determine trend based on recent closes
   bool uptrend = (currentClose > prevClose && prevClose > prevPrevClose);
   bool downtrend = (currentClose < prevClose && prevClose < prevPrevClose);
   
   // Buy signal: Uptrend + breakout above previous high + strong bullish candle
   if(uptrend && currentClose > prevHigh && currentBody > prevBody * 1.2)
   {
      // Check for fake breakout patterns
      if(IsFakeBreakout(1))
      {
         Print("Buy signal ignored due to fake breakout pattern");
         return 0;
      }
      
      // Confirm breakout validity
      if(!ConfirmBreakout(1))
      {
         Print("Buy signal waiting for confirmation");
         return 0;
      }
      
      Print("Buy signal detected - Confirmed uptrend breakout");
      return 1;
   }
   
   // Sell signal: Downtrend + breakdown below previous low + strong bearish candle
   if(downtrend && currentClose < prevLow && currentBody > prevBody * 1.2)
   {
      // Check for fake breakout patterns
      if(IsFakeBreakout(-1))
      {
         Print("Sell signal ignored due to fake breakout pattern");
         return 0;
      }
      
      // Confirm breakout validity
      if(!ConfirmBreakout(-1))
      {
         Print("Sell signal waiting for confirmation");
         return 0;
      }
      
      Print("Sell signal detected - Confirmed downtrend breakdown");
      return -1;
   }
   
   return 0; // No signal
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk management                      |
//+------------------------------------------------------------------+
double CalculateLotSize()
{
   if(!UseDynamicLot)
      return LotSize;
   
   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = accountBalance * (RiskPercent / 100.0);
   
   double pointValue = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(tickSize == 0 || tickValue == 0)
      return LotSize;
   
   double stopLossInTicks = StopLossPoints * pointValue / tickSize;
   double lotSize = riskAmount / (stopLossInTicks * tickValue);
   
   // Normalize lot size according to symbol specifications
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathFloor(lotSize / lotStep) * lotStep;
   lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
   
   return lotSize;
}

//+------------------------------------------------------------------+
//| Open buy order                                                    |
//+------------------------------------------------------------------+
void OpenBuyOrder()
{
   double lotSize = CalculateLotSize();
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   
   double stopLoss = ask - StopLossPoints * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double takeProfit = ask + TakeProfitPoints * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   
   // Normalize prices
   stopLoss = NormalizeDouble(stopLoss, _Digits);
   takeProfit = NormalizeDouble(takeProfit, _Digits);
   
   if(trade.Buy(lotSize, _Symbol, ask, stopLoss, takeProfit, "Gold Bot - Buy Signal"))
   {
      dailyTradeCount++;
      Print("Buy order opened successfully. Ticket: ", trade.ResultOrder(), 
            " | Lots: ", lotSize, " | SL: ", stopLoss, " | TP: ", takeProfit);
   }
   else
   {
      Print("Failed to open buy order. Error: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Open sell order                                                   |
//+------------------------------------------------------------------+
void OpenSellOrder()
{
   double lotSize = CalculateLotSize();
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   double stopLoss = bid + StopLossPoints * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double takeProfit = bid - TakeProfitPoints * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   
   // Normalize prices
   stopLoss = NormalizeDouble(stopLoss, _Digits);
   takeProfit = NormalizeDouble(takeProfit, _Digits);
   
   if(trade.Sell(lotSize, _Symbol, bid, stopLoss, takeProfit, "Gold Bot - Sell Signal"))
   {
      dailyTradeCount++;
      Print("Sell order opened successfully. Ticket: ", trade.ResultOrder(), 
            " | Lots: ", lotSize, " | SL: ", stopLoss, " | TP: ", takeProfit);
   }
   else
   {
      Print("Failed to open sell order. Error: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Manage existing positions (trailing stop, etc.)                  |
//+------------------------------------------------------------------+
void ManagePositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || 
         PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      
      long positionType = PositionGetInteger(POSITION_TYPE);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      
      if(positionType == POSITION_TYPE_BUY)
      {
         double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double newSL = currentPrice - StopLossPoints * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         
         // Trail stop loss if profitable
         if(newSL > currentSL && newSL > openPrice)
         {
            newSL = NormalizeDouble(newSL, _Digits);
            if(trade.PositionModify(ticket, newSL, currentTP))
            {
               Print("Trailing stop updated for buy position. New SL: ", newSL);
            }
         }
      }
      else if(positionType == POSITION_TYPE_SELL)
      {
         double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double newSL = currentPrice + StopLossPoints * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         
         // Trail stop loss if profitable
         if((newSL < currentSL || currentSL == 0) && newSL < openPrice)
         {
            newSL = NormalizeDouble(newSL, _Digits);
            if(trade.PositionModify(ticket, newSL, currentTP))
            {
               Print("Trailing stop updated for sell position. New SL: ", newSL);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Convert datetime to struct                                       |
//+------------------------------------------------------------------+
datetime StructToTime(const MqlDateTime &dt)
{
   return StructToTime(dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
}
