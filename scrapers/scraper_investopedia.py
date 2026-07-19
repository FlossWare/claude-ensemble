#!/usr/bin/env python3
"""Investopedia documentation scraper.

Covers:
  - Economics: micro/macro, GDP, inflation, monetary/fiscal policy, trade
  - Finance: financial statements, valuation, DCF, CAPM, derivatives, bonds
  - Investing: stocks, bonds, ETFs, technical/fundamental analysis
  - Personal Finance: budgeting, credit, mortgages, retirement planning
  - Accounting: GAAP, bookkeeping, depreciation, auditing
  - Banking: commercial, investment, retail, FDIC
  - Key terms/glossary: 200+ important financial terms
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class InvestopediaScraper(BaseScraper):
    """Scrape Investopedia articles, terms, and guides."""

    SOURCES = {
        "economics": {
            "pages": {
                # Microeconomics
                "https://www.investopedia.com/terms/m/microeconomics.asp": "Microeconomics",
                "https://www.investopedia.com/terms/s/supply.asp": "Supply",
                "https://www.investopedia.com/terms/d/demand.asp": "Demand",
                "https://www.investopedia.com/terms/l/law-of-supply-demand.asp": "Law of Supply and Demand",
                "https://www.investopedia.com/terms/e/elasticity.asp": "Elasticity",
                "https://www.investopedia.com/terms/p/priceelasticity.asp": "Price Elasticity of Demand",
                "https://www.investopedia.com/terms/m/marginalutility.asp": "Marginal Utility",
                "https://www.investopedia.com/terms/d/diminishingmarginalutility.asp": "Diminishing Marginal Utility",
                "https://www.investopedia.com/terms/o/opportunitycost.asp": "Opportunity Cost",
                "https://www.investopedia.com/terms/c/comparativeadvantage.asp": "Comparative Advantage",
                "https://www.investopedia.com/terms/m/marketstructure.asp": "Market Structure",
                "https://www.investopedia.com/terms/p/perfectcompetition.asp": "Perfect Competition",
                "https://www.investopedia.com/terms/m/monopoly.asp": "Monopoly",
                "https://www.investopedia.com/terms/o/oligopoly.asp": "Oligopoly",
                "https://www.investopedia.com/terms/m/monopolisticmarket.asp": "Monopolistic Competition",
                "https://www.investopedia.com/terms/e/externality.asp": "Externality",
                "https://www.investopedia.com/terms/p/public-good.asp": "Public Good",
                "https://www.investopedia.com/terms/m/marketfailure.asp": "Market Failure",
                # Macroeconomics
                "https://www.investopedia.com/terms/m/macroeconomics.asp": "Macroeconomics",
                "https://www.investopedia.com/terms/g/gdp.asp": "Gross Domestic Product (GDP)",
                "https://www.investopedia.com/terms/g/gnp.asp": "Gross National Product (GNP)",
                "https://www.investopedia.com/terms/i/inflation.asp": "Inflation",
                "https://www.investopedia.com/terms/d/deflation.asp": "Deflation",
                "https://www.investopedia.com/terms/s/stagflation.asp": "Stagflation",
                "https://www.investopedia.com/terms/h/hyperinflation.asp": "Hyperinflation",
                "https://www.investopedia.com/terms/c/consumerpriceindex.asp": "Consumer Price Index (CPI)",
                "https://www.investopedia.com/terms/p/ppi.asp": "Producer Price Index (PPI)",
                "https://www.investopedia.com/terms/u/unemploymentrate.asp": "Unemployment Rate",
                "https://www.investopedia.com/terms/n/naturalunemployment.asp": "Natural Unemployment",
                "https://www.investopedia.com/terms/f/frictionalunemployment.asp": "Frictional Unemployment",
                "https://www.investopedia.com/terms/s/structuralunemployment.asp": "Structural Unemployment",
                "https://www.investopedia.com/terms/c/cyclicalunemployment.asp": "Cyclical Unemployment",
                "https://www.investopedia.com/terms/b/businesscycle.asp": "Business Cycle",
                "https://www.investopedia.com/terms/r/recession.asp": "Recession",
                "https://www.investopedia.com/terms/d/depression.asp": "Depression",
                "https://www.investopedia.com/terms/e/economic-recovery.asp": "Economic Recovery",
                "https://www.investopedia.com/terms/e/economicindicator.asp": "Economic Indicator",
                "https://www.investopedia.com/terms/l/leadingindicator.asp": "Leading Indicator",
                "https://www.investopedia.com/terms/l/laggingindicator.asp": "Lagging Indicator",
                # Monetary and Fiscal Policy
                "https://www.investopedia.com/terms/m/monetarypolicy.asp": "Monetary Policy",
                "https://www.investopedia.com/terms/f/fiscalpolicy.asp": "Fiscal Policy",
                "https://www.investopedia.com/terms/f/federalreservebank.asp": "Federal Reserve",
                "https://www.investopedia.com/terms/c/centralbank.asp": "Central Bank",
                "https://www.investopedia.com/terms/f/federalfundsrate.asp": "Federal Funds Rate",
                "https://www.investopedia.com/terms/i/interestrate.asp": "Interest Rate",
                "https://www.investopedia.com/terms/m/moneysupply.asp": "Money Supply",
                "https://www.investopedia.com/terms/q/quantitative-easing.asp": "Quantitative Easing",
                "https://www.investopedia.com/terms/o/openmarketoperations.asp": "Open Market Operations",
                "https://www.investopedia.com/terms/r/requiredreserves.asp": "Reserve Requirements",
                "https://www.investopedia.com/terms/d/discountrate.asp": "Discount Rate",
                "https://www.investopedia.com/terms/t/taylorsrule.asp": "Taylor Rule",
                "https://www.investopedia.com/terms/p/phillipscurve.asp": "Phillips Curve",
                # International Trade and Economics
                "https://www.investopedia.com/terms/i/international-trade.asp": "International Trade",
                "https://www.investopedia.com/terms/b/bop.asp": "Balance of Payments",
                "https://www.investopedia.com/terms/c/currentaccount.asp": "Current Account",
                "https://www.investopedia.com/terms/t/trade-deficit.asp": "Trade Deficit",
                "https://www.investopedia.com/terms/t/trade-surplus.asp": "Trade Surplus",
                "https://www.investopedia.com/terms/t/tariff.asp": "Tariff",
                "https://www.investopedia.com/terms/e/exchangerate.asp": "Exchange Rate",
                "https://www.investopedia.com/terms/f/floatingexchangerate.asp": "Floating Exchange Rate",
                "https://www.investopedia.com/terms/f/fixedexchangerate.asp": "Fixed Exchange Rate",
                "https://www.investopedia.com/terms/p/purchasingpower.asp": "Purchasing Power",
                "https://www.investopedia.com/terms/p/ppp.asp": "Purchasing Power Parity",
                "https://www.investopedia.com/terms/f/freetradeagreement.asp": "Free Trade Agreement",
                "https://www.investopedia.com/terms/p/protectionism.asp": "Protectionism",
            },
        },
        "finance": {
            "pages": {
                # Financial Statements
                "https://www.investopedia.com/terms/f/financial-statements.asp": "Financial Statements",
                "https://www.investopedia.com/terms/i/incomestatement.asp": "Income Statement",
                "https://www.investopedia.com/terms/b/balancesheet.asp": "Balance Sheet",
                "https://www.investopedia.com/terms/c/cashflowstatement.asp": "Cash Flow Statement",
                "https://www.investopedia.com/terms/r/revenue.asp": "Revenue",
                "https://www.investopedia.com/terms/c/cogs.asp": "Cost of Goods Sold (COGS)",
                "https://www.investopedia.com/terms/g/grossprofit.asp": "Gross Profit",
                "https://www.investopedia.com/terms/o/operatingincome.asp": "Operating Income",
                "https://www.investopedia.com/terms/n/netincome.asp": "Net Income",
                "https://www.investopedia.com/terms/e/ebitda.asp": "EBITDA",
                "https://www.investopedia.com/terms/e/eps.asp": "Earnings Per Share (EPS)",
                "https://www.investopedia.com/terms/r/retainedearnings.asp": "Retained Earnings",
                # Ratio Analysis
                "https://www.investopedia.com/terms/f/financialratio.asp": "Financial Ratio",
                "https://www.investopedia.com/terms/p/price-earningsratio.asp": "Price-to-Earnings Ratio (P/E)",
                "https://www.investopedia.com/terms/p/price-to-bookratio.asp": "Price-to-Book Ratio (P/B)",
                "https://www.investopedia.com/terms/d/debtequityratio.asp": "Debt-to-Equity Ratio",
                "https://www.investopedia.com/terms/c/currentratio.asp": "Current Ratio",
                "https://www.investopedia.com/terms/q/quickratio.asp": "Quick Ratio",
                "https://www.investopedia.com/terms/r/returnonequity.asp": "Return on Equity (ROE)",
                "https://www.investopedia.com/terms/r/returnonassets.asp": "Return on Assets (ROA)",
                "https://www.investopedia.com/terms/r/roic.asp": "Return on Invested Capital (ROIC)",
                "https://www.investopedia.com/terms/g/grossmargin.asp": "Gross Margin",
                "https://www.investopedia.com/terms/o/operatingmargin.asp": "Operating Margin",
                "https://www.investopedia.com/terms/n/net_margin.asp": "Net Profit Margin",
                # Valuation
                "https://www.investopedia.com/terms/v/valuation.asp": "Valuation",
                "https://www.investopedia.com/terms/d/dcf.asp": "Discounted Cash Flow (DCF)",
                "https://www.investopedia.com/terms/n/npv.asp": "Net Present Value (NPV)",
                "https://www.investopedia.com/terms/i/irr.asp": "Internal Rate of Return (IRR)",
                "https://www.investopedia.com/terms/p/presentvalue.asp": "Present Value",
                "https://www.investopedia.com/terms/f/futurevalue.asp": "Future Value",
                "https://www.investopedia.com/terms/t/timevalueofmoney.asp": "Time Value of Money",
                "https://www.investopedia.com/terms/w/wacc.asp": "Weighted Average Cost of Capital (WACC)",
                "https://www.investopedia.com/terms/c/capm.asp": "Capital Asset Pricing Model (CAPM)",
                "https://www.investopedia.com/terms/b/beta.asp": "Beta",
                "https://www.investopedia.com/terms/e/equityriskpremium.asp": "Equity Risk Premium",
                "https://www.investopedia.com/terms/c/costofcapital.asp": "Cost of Capital",
                "https://www.investopedia.com/terms/e/enterprisevalue.asp": "Enterprise Value",
                # Portfolio Theory and Risk
                "https://www.investopedia.com/terms/m/modernportfoliotheory.asp": "Modern Portfolio Theory",
                "https://www.investopedia.com/terms/e/efficientfrontier.asp": "Efficient Frontier",
                "https://www.investopedia.com/terms/a/assetallocation.asp": "Asset Allocation",
                "https://www.investopedia.com/terms/d/diversification.asp": "Diversification",
                "https://www.investopedia.com/terms/r/riskmanagement.asp": "Risk Management",
                "https://www.investopedia.com/terms/s/sharperatio.asp": "Sharpe Ratio",
                "https://www.investopedia.com/terms/s/standarddeviation.asp": "Standard Deviation",
                "https://www.investopedia.com/terms/v/variance.asp": "Variance",
                "https://www.investopedia.com/terms/c/correlation.asp": "Correlation",
                "https://www.investopedia.com/terms/s/systematicrisk.asp": "Systematic Risk",
                "https://www.investopedia.com/terms/u/unsystematicrisk.asp": "Unsystematic Risk",
                "https://www.investopedia.com/terms/v/var.asp": "Value at Risk (VaR)",
                # Derivatives
                "https://www.investopedia.com/terms/d/derivative.asp": "Derivative",
                "https://www.investopedia.com/terms/o/option.asp": "Option",
                "https://www.investopedia.com/terms/c/calloption.asp": "Call Option",
                "https://www.investopedia.com/terms/p/putoption.asp": "Put Option",
                "https://www.investopedia.com/terms/s/strikeprice.asp": "Strike Price",
                "https://www.investopedia.com/terms/e/expirationdate.asp": "Expiration Date",
                "https://www.investopedia.com/terms/i/intrinsicvalue.asp": "Intrinsic Value",
                "https://www.investopedia.com/terms/t/timevalue.asp": "Time Value",
                "https://www.investopedia.com/terms/b/blackscholes.asp": "Black-Scholes Model",
                "https://www.investopedia.com/terms/g/greeks.asp": "The Greeks (Options)",
                "https://www.investopedia.com/terms/f/futurescontract.asp": "Futures Contract",
                "https://www.investopedia.com/terms/f/forwardcontract.asp": "Forward Contract",
                "https://www.investopedia.com/terms/s/swap.asp": "Swap",
                "https://www.investopedia.com/terms/i/interestrateswap.asp": "Interest Rate Swap",
                "https://www.investopedia.com/terms/c/creditdefaultswap.asp": "Credit Default Swap",
                "https://www.investopedia.com/terms/h/hedge.asp": "Hedge",
                # Bonds and Fixed Income
                "https://www.investopedia.com/terms/b/bond.asp": "Bond",
                "https://www.investopedia.com/terms/c/couponrate.asp": "Coupon Rate",
                "https://www.investopedia.com/terms/y/yield.asp": "Yield",
                "https://www.investopedia.com/terms/y/yieldtomaturity.asp": "Yield to Maturity",
                "https://www.investopedia.com/terms/y/yieldcurve.asp": "Yield Curve",
                "https://www.investopedia.com/terms/i/invertedyieldcurve.asp": "Inverted Yield Curve",
                "https://www.investopedia.com/terms/d/duration.asp": "Duration",
                "https://www.investopedia.com/terms/c/creditrating.asp": "Credit Rating",
                "https://www.investopedia.com/terms/c/creditspread.asp": "Credit Spread",
                "https://www.investopedia.com/terms/t/treasurybond.asp": "Treasury Bond",
                "https://www.investopedia.com/terms/m/municipalbond.asp": "Municipal Bond",
                "https://www.investopedia.com/terms/c/corporatebond.asp": "Corporate Bond",
                "https://www.investopedia.com/terms/j/junkbond.asp": "Junk Bond",
                "https://www.investopedia.com/terms/z/zero-couponbond.asp": "Zero-Coupon Bond",
                "https://www.investopedia.com/terms/c/convertiblebond.asp": "Convertible Bond",
                "https://www.investopedia.com/terms/f/fixedincome.asp": "Fixed Income",
            },
        },
        "investing": {
            "pages": {
                # Stocks
                "https://www.investopedia.com/terms/s/stock.asp": "Stock",
                "https://www.investopedia.com/terms/c/commonstock.asp": "Common Stock",
                "https://www.investopedia.com/terms/p/preferredstock.asp": "Preferred Stock",
                "https://www.investopedia.com/terms/m/marketcapitalization.asp": "Market Capitalization",
                "https://www.investopedia.com/terms/d/dividend.asp": "Dividend",
                "https://www.investopedia.com/terms/d/dividendyield.asp": "Dividend Yield",
                "https://www.investopedia.com/terms/s/stocksplit.asp": "Stock Split",
                "https://www.investopedia.com/terms/s/sharerepurchase.asp": "Share Buyback",
                "https://www.investopedia.com/terms/i/ipo.asp": "Initial Public Offering (IPO)",
                "https://www.investopedia.com/terms/s/secondarymarket.asp": "Secondary Market",
                "https://www.investopedia.com/terms/b/bluechipstock.asp": "Blue Chip Stock",
                "https://www.investopedia.com/terms/p/pennystock.asp": "Penny Stock",
                "https://www.investopedia.com/terms/g/growthstock.asp": "Growth Stock",
                "https://www.investopedia.com/terms/v/valuestock.asp": "Value Stock",
                # Investment Vehicles
                "https://www.investopedia.com/terms/m/mutualfund.asp": "Mutual Fund",
                "https://www.investopedia.com/terms/e/etf.asp": "Exchange-Traded Fund (ETF)",
                "https://www.investopedia.com/terms/i/indexfund.asp": "Index Fund",
                "https://www.investopedia.com/terms/h/hedgefund.asp": "Hedge Fund",
                "https://www.investopedia.com/terms/r/reit.asp": "Real Estate Investment Trust (REIT)",
                "https://www.investopedia.com/terms/c/closed-endinvestment.asp": "Closed-End Fund",
                "https://www.investopedia.com/terms/t/targetdatefund.asp": "Target-Date Fund",
                "https://www.investopedia.com/terms/m/moneymarketfund.asp": "Money Market Fund",
                # Trading and Orders
                "https://www.investopedia.com/terms/m/marketorder.asp": "Market Order",
                "https://www.investopedia.com/terms/l/limitorder.asp": "Limit Order",
                "https://www.investopedia.com/terms/s/stoporder.asp": "Stop Order",
                "https://www.investopedia.com/terms/s/stop-lossorder.asp": "Stop-Loss Order",
                "https://www.investopedia.com/terms/s/shortselling.asp": "Short Selling",
                "https://www.investopedia.com/terms/m/margin.asp": "Margin",
                "https://www.investopedia.com/terms/b/bid-askspread.asp": "Bid-Ask Spread",
                "https://www.investopedia.com/terms/v/volume.asp": "Volume",
                "https://www.investopedia.com/terms/l/liquidity.asp": "Liquidity",
                # Technical Analysis
                "https://www.investopedia.com/terms/t/technicalanalysis.asp": "Technical Analysis",
                "https://www.investopedia.com/terms/m/movingaverage.asp": "Moving Average",
                "https://www.investopedia.com/terms/r/rsi.asp": "Relative Strength Index (RSI)",
                "https://www.investopedia.com/terms/m/macd.asp": "MACD",
                "https://www.investopedia.com/terms/b/bollingerbands.asp": "Bollinger Bands",
                "https://www.investopedia.com/terms/s/supportandresistance.asp": "Support and Resistance",
                "https://www.investopedia.com/terms/c/candlestick.asp": "Candlestick Chart",
                "https://www.investopedia.com/terms/h/head-shoulders.asp": "Head and Shoulders Pattern",
                "https://www.investopedia.com/terms/f/fibonacciretracement.asp": "Fibonacci Retracement",
                # Fundamental Analysis
                "https://www.investopedia.com/terms/f/fundamentalanalysis.asp": "Fundamental Analysis",
                "https://www.investopedia.com/terms/v/valueinvesting.asp": "Value Investing",
                "https://www.investopedia.com/terms/g/growthinvesting.asp": "Growth Investing",
                "https://www.investopedia.com/terms/b/buyandhold.asp": "Buy and Hold",
                "https://www.investopedia.com/terms/d/dollarcostaveraging.asp": "Dollar Cost Averaging",
                "https://www.investopedia.com/terms/d/daytrader.asp": "Day Trading",
                "https://www.investopedia.com/terms/s/swingtrading.asp": "Swing Trading",
                "https://www.investopedia.com/terms/r/rebalancing.asp": "Rebalancing",
                "https://www.investopedia.com/terms/t/taxgainlossharvesting.asp": "Tax-Loss Harvesting",
                "https://www.investopedia.com/terms/b/benchmarking.asp": "Benchmarking",
            },
        },
        "personal-finance": {
            "pages": {
                # Budgeting and Savings
                "https://www.investopedia.com/terms/b/budget.asp": "Budget",
                "https://www.investopedia.com/terms/e/emergencyfund.asp": "Emergency Fund",
                "https://www.investopedia.com/terms/s/savings-account.asp": "Savings Account",
                "https://www.investopedia.com/terms/c/compoundinterest.asp": "Compound Interest",
                "https://www.investopedia.com/terms/s/simpleinterest.asp": "Simple Interest",
                "https://www.investopedia.com/terms/n/networthcertificate.asp": "Net Worth",
                # Credit and Debt
                "https://www.investopedia.com/terms/c/credit.asp": "Credit",
                "https://www.investopedia.com/terms/c/credit-score.asp": "Credit Score",
                "https://www.investopedia.com/terms/c/creditreport.asp": "Credit Report",
                "https://www.investopedia.com/terms/c/creditcard.asp": "Credit Card",
                "https://www.investopedia.com/terms/a/apr.asp": "Annual Percentage Rate (APR)",
                "https://www.investopedia.com/terms/a/apy.asp": "Annual Percentage Yield (APY)",
                "https://www.investopedia.com/terms/d/debt.asp": "Debt",
                "https://www.investopedia.com/terms/d/debtconsolidation.asp": "Debt Consolidation",
                "https://www.investopedia.com/terms/b/bankruptcy.asp": "Bankruptcy",
                "https://www.investopedia.com/terms/c/chapter7.asp": "Chapter 7 Bankruptcy",
                "https://www.investopedia.com/terms/c/chapter13.asp": "Chapter 13 Bankruptcy",
                # Mortgages and Real Estate
                "https://www.investopedia.com/terms/m/mortgage.asp": "Mortgage",
                "https://www.investopedia.com/terms/f/fixed-rate_mortgage.asp": "Fixed-Rate Mortgage",
                "https://www.investopedia.com/terms/a/arm.asp": "Adjustable-Rate Mortgage (ARM)",
                "https://www.investopedia.com/terms/r/refinance.asp": "Refinance",
                "https://www.investopedia.com/terms/d/downpayment.asp": "Down Payment",
                "https://www.investopedia.com/terms/e/equity.asp": "Equity",
                "https://www.investopedia.com/terms/a/amortization.asp": "Amortization",
                "https://www.investopedia.com/terms/e/escrow.asp": "Escrow",
                "https://www.investopedia.com/terms/p/pmi.asp": "Private Mortgage Insurance (PMI)",
                # Insurance
                "https://www.investopedia.com/terms/i/insurance.asp": "Insurance",
                "https://www.investopedia.com/terms/l/lifeinsurance.asp": "Life Insurance",
                "https://www.investopedia.com/terms/t/termlife.asp": "Term Life Insurance",
                "https://www.investopedia.com/terms/w/wholelife.asp": "Whole Life Insurance",
                "https://www.investopedia.com/terms/h/healthinsurance.asp": "Health Insurance",
                "https://www.investopedia.com/terms/d/disability-insurance.asp": "Disability Insurance",
                "https://www.investopedia.com/terms/h/homeowners-insurance.asp": "Homeowners Insurance",
                "https://www.investopedia.com/terms/a/auto-insurance.asp": "Auto Insurance",
                "https://www.investopedia.com/terms/u/umbrellainsurance.asp": "Umbrella Insurance",
                # Retirement Planning
                "https://www.investopedia.com/terms/1/401kplan.asp": "401(k) Plan",
                "https://www.investopedia.com/terms/i/ira.asp": "Individual Retirement Account (IRA)",
                "https://www.investopedia.com/terms/r/rothira.asp": "Roth IRA",
                "https://www.investopedia.com/terms/t/traditionalira.asp": "Traditional IRA",
                "https://www.investopedia.com/terms/4/403bplan.asp": "403(b) Plan",
                "https://www.investopedia.com/terms/p/pensionplan.asp": "Pension Plan",
                "https://www.investopedia.com/terms/s/socialsecurity.asp": "Social Security",
                "https://www.investopedia.com/terms/a/annuity.asp": "Annuity",
                "https://www.investopedia.com/terms/r/requiredminimumdistribution.asp": "Required Minimum Distribution (RMD)",
                # Estate Planning
                "https://www.investopedia.com/terms/e/estateplanning.asp": "Estate Planning",
                "https://www.investopedia.com/terms/w/will.asp": "Will",
                "https://www.investopedia.com/terms/t/trust.asp": "Trust",
                "https://www.investopedia.com/terms/e/estatetax.asp": "Estate Tax",
                "https://www.investopedia.com/terms/p/powerofattorney.asp": "Power of Attorney",
                "https://www.investopedia.com/terms/b/beneficiary.asp": "Beneficiary",
                # Taxes
                "https://www.investopedia.com/terms/t/taxbracket.asp": "Tax Bracket",
                "https://www.investopedia.com/terms/p/progressivetax.asp": "Progressive Tax",
                "https://www.investopedia.com/terms/c/capitalgain.asp": "Capital Gains Tax",
                "https://www.investopedia.com/terms/t/taxdeduction.asp": "Tax Deduction",
                "https://www.investopedia.com/terms/t/taxcredit.asp": "Tax Credit",
                "https://www.investopedia.com/terms/s/standarddeduction.asp": "Standard Deduction",
                "https://www.investopedia.com/terms/i/itemizeddeduction.asp": "Itemized Deduction",
                "https://www.investopedia.com/terms/w/w2form.asp": "W-2 Form",
                "https://www.investopedia.com/terms/1/1099-misc.asp": "1099 Form",
            },
        },
        "accounting": {
            "pages": {
                # Fundamentals
                "https://www.investopedia.com/terms/a/accounting.asp": "Accounting",
                "https://www.investopedia.com/terms/g/gaap.asp": "Generally Accepted Accounting Principles (GAAP)",
                "https://www.investopedia.com/terms/i/ifrs.asp": "International Financial Reporting Standards (IFRS)",
                "https://www.investopedia.com/terms/a/accrualaccounting.asp": "Accrual Accounting",
                "https://www.investopedia.com/terms/c/cashaccounting.asp": "Cash Accounting",
                "https://www.investopedia.com/terms/d/double-entry.asp": "Double-Entry Bookkeeping",
                "https://www.investopedia.com/terms/j/journal.asp": "Journal Entry",
                "https://www.investopedia.com/terms/g/generalledger.asp": "General Ledger",
                "https://www.investopedia.com/terms/t/trialbalance.asp": "Trial Balance",
                "https://www.investopedia.com/terms/c/chartofaccounts.asp": "Chart of Accounts",
                # Assets and Liabilities
                "https://www.investopedia.com/terms/a/asset.asp": "Asset",
                "https://www.investopedia.com/terms/l/liability.asp": "Liability",
                "https://www.investopedia.com/terms/s/shareholdersequity.asp": "Shareholders Equity",
                "https://www.investopedia.com/terms/a/accountsreceivable.asp": "Accounts Receivable",
                "https://www.investopedia.com/terms/a/accountspayable.asp": "Accounts Payable",
                "https://www.investopedia.com/terms/d/depreciation.asp": "Depreciation",
                "https://www.investopedia.com/terms/a/amortization.asp": "Amortization (Accounting)",
                "https://www.investopedia.com/terms/g/goodwill.asp": "Goodwill",
                "https://www.investopedia.com/terms/i/inventory.asp": "Inventory",
                "https://www.investopedia.com/terms/f/fifo.asp": "FIFO (First In First Out)",
                "https://www.investopedia.com/terms/l/lifo.asp": "LIFO (Last In First Out)",
                # Cost Accounting
                "https://www.investopedia.com/terms/c/cost-accounting.asp": "Cost Accounting",
                "https://www.investopedia.com/terms/f/fixedcost.asp": "Fixed Cost",
                "https://www.investopedia.com/terms/v/variablecost.asp": "Variable Cost",
                "https://www.investopedia.com/terms/o/overhead.asp": "Overhead",
                "https://www.investopedia.com/terms/b/breakevenpoint.asp": "Break-Even Point",
                "https://www.investopedia.com/terms/c/contributionmargin.asp": "Contribution Margin",
                # Auditing
                "https://www.investopedia.com/terms/a/audit.asp": "Audit",
                "https://www.investopedia.com/terms/i/internalaudit.asp": "Internal Audit",
                "https://www.investopedia.com/terms/e/externalauditor.asp": "External Auditor",
                "https://www.investopedia.com/terms/m/materialityprinciple.asp": "Materiality",
                "https://www.investopedia.com/terms/s/sarbanesoxleyact.asp": "Sarbanes-Oxley Act",
            },
        },
        "banking": {
            "pages": {
                "https://www.investopedia.com/terms/c/commercialbank.asp": "Commercial Bank",
                "https://www.investopedia.com/terms/i/investmentbank.asp": "Investment Bank",
                "https://www.investopedia.com/terms/r/retailbanking.asp": "Retail Banking",
                "https://www.investopedia.com/terms/c/creditunion.asp": "Credit Union",
                "https://www.investopedia.com/terms/f/fdic.asp": "Federal Deposit Insurance Corporation (FDIC)",
                "https://www.investopedia.com/terms/f/fractionalreservebanking.asp": "Fractional Reserve Banking",
                "https://www.investopedia.com/terms/m/moneymarket.asp": "Money Market",
                "https://www.investopedia.com/terms/c/certificateofdeposit.asp": "Certificate of Deposit (CD)",
                "https://www.investopedia.com/terms/c/checkingaccount.asp": "Checking Account",
                "https://www.investopedia.com/terms/h/hysa.asp": "High-Yield Savings Account",
                "https://www.investopedia.com/terms/w/wiretransfer.asp": "Wire Transfer",
                "https://www.investopedia.com/terms/a/ach.asp": "Automated Clearing House (ACH)",
                "https://www.investopedia.com/terms/o/overdraft.asp": "Overdraft",
                "https://www.investopedia.com/terms/p/primerate.asp": "Prime Rate",
                "https://www.investopedia.com/terms/l/libor.asp": "LIBOR",
                "https://www.investopedia.com/terms/s/sofr.asp": "SOFR",
            },
        },
        "glossary": {
            "pages": {
                # Core financial terms A-Z
                "https://www.investopedia.com/terms/a/absoluteadvantage.asp": "Absolute Advantage",
                "https://www.investopedia.com/terms/a/accruedinterest.asp": "Accrued Interest",
                "https://www.investopedia.com/terms/a/alpha.asp": "Alpha",
                "https://www.investopedia.com/terms/a/arbitrage.asp": "Arbitrage",
                "https://www.investopedia.com/terms/a/askprice.asp": "Ask Price",
                "https://www.investopedia.com/terms/b/bearmarket.asp": "Bear Market",
                "https://www.investopedia.com/terms/b/bidprice.asp": "Bid Price",
                "https://www.investopedia.com/terms/b/bullmarket.asp": "Bull Market",
                "https://www.investopedia.com/terms/b/bubble.asp": "Bubble",
                "https://www.investopedia.com/terms/c/capitalbudgeting.asp": "Capital Budgeting",
                "https://www.investopedia.com/terms/c/capitalexpenditure.asp": "Capital Expenditure (CapEx)",
                "https://www.investopedia.com/terms/c/capitalgainsloss.asp": "Capital Gains/Loss",
                "https://www.investopedia.com/terms/c/cashflow.asp": "Cash Flow",
                "https://www.investopedia.com/terms/c/collateral.asp": "Collateral",
                "https://www.investopedia.com/terms/c/commodity.asp": "Commodity",
                "https://www.investopedia.com/terms/c/conglomerate.asp": "Conglomerate",
                "https://www.investopedia.com/terms/c/contingentliability.asp": "Contingent Liability",
                "https://www.investopedia.com/terms/c/costofliving.asp": "Cost of Living",
                "https://www.investopedia.com/terms/c/currency.asp": "Currency",
                "https://www.investopedia.com/terms/d/default2.asp": "Default",
                "https://www.investopedia.com/terms/d/deficit.asp": "Deficit",
                "https://www.investopedia.com/terms/d/disinflation.asp": "Disinflation",
                "https://www.investopedia.com/terms/d/duediligence.asp": "Due Diligence",
                "https://www.investopedia.com/terms/e/economics.asp": "Economics",
                "https://www.investopedia.com/terms/e/economy.asp": "Economy",
                "https://www.investopedia.com/terms/e/equitymarket.asp": "Equity Market",
                "https://www.investopedia.com/terms/f/fiduciary.asp": "Fiduciary",
                "https://www.investopedia.com/terms/f/float.asp": "Float",
                "https://www.investopedia.com/terms/f/foreclosure.asp": "Foreclosure",
                "https://www.investopedia.com/terms/f/freecashflow.asp": "Free Cash Flow",
                "https://www.investopedia.com/terms/f/fundamentals.asp": "Fundamentals",
                "https://www.investopedia.com/terms/g/gdpgap.asp": "GDP Gap",
                "https://www.investopedia.com/terms/g/gini-index.asp": "Gini Index",
                "https://www.investopedia.com/terms/g/golden-parachute.asp": "Golden Parachute",
                "https://www.investopedia.com/terms/h/hdi.asp": "Human Development Index",
                "https://www.investopedia.com/terms/i/incometax.asp": "Income Tax",
                "https://www.investopedia.com/terms/i/insidertrading.asp": "Insider Trading",
                "https://www.investopedia.com/terms/i/inflationrate.asp": "Inflation Rate",
                "https://www.investopedia.com/terms/k/keynesianeconomics.asp": "Keynesian Economics",
                "https://www.investopedia.com/terms/l/leverage.asp": "Leverage",
                "https://www.investopedia.com/terms/l/liquidation.asp": "Liquidation",
                "https://www.investopedia.com/terms/m/mergersandacquisitions.asp": "Mergers and Acquisitions (M&A)",
                "https://www.investopedia.com/terms/m/moralhazard.asp": "Moral Hazard",
                "https://www.investopedia.com/terms/n/nominalgdp.asp": "Nominal GDP",
                "https://www.investopedia.com/terms/o/overbought.asp": "Overbought",
                "https://www.investopedia.com/terms/o/oversold.asp": "Oversold",
                "https://www.investopedia.com/terms/p/payoutratio.asp": "Payout Ratio",
                "https://www.investopedia.com/terms/p/ponzischeme.asp": "Ponzi Scheme",
                "https://www.investopedia.com/terms/p/portfolio.asp": "Portfolio",
                "https://www.investopedia.com/terms/p/principal.asp": "Principal",
                "https://www.investopedia.com/terms/p/profitmargin.asp": "Profit Margin",
                "https://www.investopedia.com/terms/r/realgdp.asp": "Real GDP",
                "https://www.investopedia.com/terms/r/recession.asp": "Recession (Glossary)",
                "https://www.investopedia.com/terms/r/revenue.asp": "Revenue (Glossary)",
                "https://www.investopedia.com/terms/r/risktolerance.asp": "Risk Tolerance",
                "https://www.investopedia.com/terms/s/sec.asp": "Securities and Exchange Commission (SEC)",
                "https://www.investopedia.com/terms/s/security.asp": "Security",
                "https://www.investopedia.com/terms/s/solvency.asp": "Solvency",
                "https://www.investopedia.com/terms/s/speculation.asp": "Speculation",
                "https://www.investopedia.com/terms/s/supplysideeconomics.asp": "Supply-Side Economics",
                "https://www.investopedia.com/terms/t/treasurybill.asp": "Treasury Bill (T-Bill)",
                "https://www.investopedia.com/terms/t/treasurynote.asp": "Treasury Note",
                "https://www.investopedia.com/terms/u/underwriting.asp": "Underwriting",
                "https://www.investopedia.com/terms/v/venturecapital.asp": "Venture Capital",
                "https://www.investopedia.com/terms/v/volatility.asp": "Volatility",
                "https://www.investopedia.com/terms/w/workingcapital.asp": "Working Capital",
                "https://www.investopedia.com/terms/y/yen.asp": "Japanese Yen",
                "https://www.investopedia.com/terms/z/zba.asp": "Zero-Balance Account",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"investopedia-{source_key}" if source_key else "investopedia"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [
                ': Definition, Formula, and Example',
                ': Definition, How It Works, and Example',
                ': Definition, Types, and Examples',
                ': Definition and Example',
                ': What It Is and How It Works',
                ': Definition, How It Works',
                ': Definition, Formula',
                ': Overview, Types',
                ' - Investopedia',
                ' | Investopedia',
            ]:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": "investopedia",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)  # Respectful rate limit

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping investopedia/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    InvestopediaScraper(base, source_key).run()
