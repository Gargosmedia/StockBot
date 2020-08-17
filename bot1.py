from bs4 import BeautifulSoup
import requests
import time
import datetime
from datetime import date, timedelta
import telegram
import apireds 

ellie = telegram.Bot(token=apireds.TELEGA_TOKEN)

screenerUrls = ['https://finviz.com/screener.ashx?v=111&f=an_recom_buybetter,sec_technology,sh_curvol_o50,sh_price_1to10,ta_rsi_os40&ft=4', 'https://finviz.com/screener.ashx?v=111&f=an_recom_buybetter,sec_technology,sh_curvol_o500,sh_price_o15,ta_rsi_os40&ft=4','https://finviz.com/screener.ashx?v=111&f=an_recom_buybetter,sec_technology,sh_curvol_o500,sh_price_o15,ta_rsi_os40&ft=4&o=-volume', 'https://finviz.com/screener.ashx?v=111&f=sh_curvol_o500,sh_price_o15,ta_highlow50d_b15h,ta_highlow52w_b20h&ft=4&o=-volume', 'https://finviz.com/screener.ashx?v=111&f=an_recom_buybetter,geo_usa,sh_curvol_o500,sh_price_o15,ta_highlow50d_b15h,ta_highlow52w_b30h&ft=4']

screenerUrlHead = ''
portfile=''

cnnURL = 'https://money.cnn.com/quote/forecast/forecast.html?symb='
tickerUrl = 'https://finviz.com/quote.ashx?t='
userAgent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'

portfolioDict = {'$':1000}
concStocks = 3 
singleStockMinBudget = 100
upperThreshold = 0.2
lowerThreshold = 0.1
cnnCoeficient=0.8  


def ParseCNN(tickers): 
    headers = { 'User-Agent' : userAgent } 
    forecastDict = {}
    orderedForecastList = []

    for ticker in tickers:
        response = requests.get(cnnURL+ticker, headers=headers) 

        try:
            forecast = response.text.split('The median estimate represents a <span class="posData">')[1].split('</span>')[0]
        except:
            forecast = 'N/A'

        if forecast.startswith('+'):
            forecast=forecast[1:-1]
            forecastDict[ticker]=float(forecast)
        else:
            print("Ticker ", ticker, ' has negative  forecast : ', forecast)

    orderingList = sorted(forecastDict, key=forecastDict.get, reverse=True)

    for i in orderingList:
        orderedForecastList.append([i, forecastDict[i]])   # [ticker, forecasted value]

    return(orderedForecastList)


def ParseScreener(url, use):
    dict={}
    headers = { 'User-Agent' : userAgent }
    response = requests.get(url, headers=headers)
    page = response.text
    soup = BeautifulSoup(page, 'html.parser')
    
    if (use == 1):
        for line in soup.findAll('tr',attrs={"class":"table-dark-row-cp"}):

            lineAttrs = line.findAll('a', attrs={"class":"screener-link"})
            attrsList=[]

            for value in line.findAll('a', attrs={"class":"screener-link"}):
                attrsList.append(value.getText())

            name = line.find('a', attrs={"class":"screener-link-primary"}).getText()
            fullName = attrsList.pop(1)
            dict[name]=attrsList

        return dict

    elif (use == 2):
        lines = soup.findAll('tr',attrs={"class":"table-dark-row"})
        fields = lines[10].findAll('b')
        price=fields[5].getText()

        return price


def ReadPortfolio():
    global portfolioDict

    try:
        with open(portfile, 'r') as portfolio:
            portfolieVar=portfolio.read()
            portfolioDict = eval(portfolieVar)
    except Exception as e:
        print("Error: ",  e)
        SendMessage(message=str(e))
        portfolioDict = {'$':1000}
        with open(portfile, 'w') as portfolio:
            portfolio.write(str(portfolioDict))
    return portfolioDict


def WritePortfolio():
    global portfolioDict
    with open(portfile, 'w') as portfolio:
        portfolio.write(str(portfolioDict))

    # print('Wrote:\n',portfolioDict, '\n--------------------------------------------------')
    BuildSendMessage()
    return portfolioDict


def BuildSendMessage():
    message = screenerUrlHead+'\n\n'
    currentAssetEstimation = portfolioDict['$']

    for key, value in portfolioDict.items():
        message += str(key) + ': ' + str(value) + '\n\n'
        if(type(value) != float):
            currentAssetEstimation += round(value['price'] * value['amount'], 2)

    message += ('========\nCAE : ' + str(round(currentAssetEstimation,2)) + '$')

    SendMessage(message=message)


def Buy(ticker,forecast, budget):
    global portfolioDict
    #Can only buy one time of one ticker - check before request. Can set to average the prices for multiple buy requests but no need
    
    if (ticker in portfolioDict and portfolioDict[ticker]['amount'] != 0):
        return portfolioDict

    money = portfolioDict['$']
    price = float(ParseScreener(tickerUrl+ticker,2))
    amount = int(budget/price)
    # print(price, ' amount: ', amount)
    #Substracting total money
    portfolioDict['$'] = round(money-(price*amount),2)
    portfolioDict[ticker]={'price': price,'amount': amount, 'predictedPercentageIncrease': round(forecast/100,2), 'dateBought': date.today(), 'dateLimitSell': (date.today() + timedelta(days=3)) }

    return WritePortfolio()


def Sell(ticker):
    global portfolioDict
    
    # print('Selling: ', ticker)
    #Only selling all of the tickers
    money = portfolioDict['$']
    amount = portfolioDict[ticker]['amount']
    price =  float(ParseScreener((tickerUrl + ticker),2))
    portfolioDict['$'] = round(money+(price*amount),2)
    #Deleting from dict
    #portfolioDict[ticker]['amount']=0
    del portfolioDict[ticker]
    return WritePortfolio()
    

def SendOrders(potentialBuyOrdered, concBuy):
    
    if (concBuy ==  0):
        return False

    while (portfolioDict['$']/concBuy < singleStockMinBudget):
        # print('Not enough money for ', concBuy, '. Downscaling to ', concBuy-1 )
        concBuy -= 1
        if (concBuy ==  0):
            return False

    # print('concbuy2: ', concBuy)
    
    budget = portfolioDict['$']/concBuy  # Can split them to len(potentialButOrdered) when its less then concStocks but to limit risk will budget to 3 even if theres only 2 to buy

    # print('Budget: ', budget)
    # print('potential list: ', potentialBuyOrdered)

    if (len(potentialBuyOrdered) >= concBuy):
        for ticker, forecast in potentialBuyOrdered[:concBuy]:
            Buy(ticker, forecast, budget)
    else:
        for ticker, forecast in potentialBuyOrdered:
            Buy(ticker, forecast, budget)

    # TODO: Look for better implementation of the check ^

    return True


def CheckSellPortfolio():
    global portfolioDict

    portfolioDictIter = portfolioDict.copy()

    for ticker, attributes in portfolioDictIter.items():
       
        if ticker != '$':
            predictedIncrease = attributes['predictedPercentageIncrease']
            priceMarket =  float(ParseScreener((tickerUrl + ticker),2))
            pricePortfolio = attributes['price']
            dateBought = attributes['dateBought']
            dateLimitSell = attributes['dateLimitSell']

            if predictedIncrease > upperThreshold:
                predictedIncrease = upperThreshold
            else:
                predictedIncrease = predictedIncrease*cnnCoeficient

            limitSellPrice = pricePortfolio*(1+predictedIncrease)
            # print(ticker,' predicted increase:', predictedIncrease, 'sell price: ', limitSellPrice, 'curr price: ', pricePortfolio)

            if (priceMarket >= limitSellPrice):
                Sell(ticker)
            elif (priceMarket < pricePortfolio*(1-lowerThreshold)):
                Sell(ticker)
            elif (dateBought >= dateLimitSell):
                Sell(ticker)
                
            # ^ Leaving ifs separate to modify later 



    return portfolioDict


def SendMessage(chatid = '561191777', message = 'Test Message'):
    #pass
    ellie.sendMessage(chatid, message)


def Main():
    global screenerUrlHead
    global portfile

    while True:

        for screenerUrl in screenerUrls:
            
            screenerUrlHead = screenerUrl
            portfile = screenerUrl.split('?')[1]+'.txt'
            ReadPortfolio()
            

            try: 
                CheckSellPortfolio()

                    # print ('len(portfolioDict)<(concStocks+1)', len(portfolioDict), ' : ', (concStocks+1))

                concBuy = concStocks - len(portfolioDict)

                if (len(portfolioDict)<(concStocks+1)):
                    potentialBuy = ParseScreener(screenerUrl, 1)
                    #print('potential buy: ', potentialBuy)

                    potentialBuyOrdered = ParseCNN(potentialBuy.keys())
                    # print('finished potential but: ', potentialBuyOrdered)
                    concBuy = concStocks - (len(portfolioDict) - 1) 
                    # print(' sent concbuy: ', concBuy)
                    SendOrders(potentialBuyOrdered, concBuy)
                
                time.sleep(15)
                
            except Exception as e:
                print("Error: ",  e)
                SendMessage(message=str(e))
                pass




Main()
