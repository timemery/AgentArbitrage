# Using Python to Work with the Keepa API to Automate MySQL Database Ingestion for Power BI

by Homegrown Development May 6, 2022

Python is a versatile language that can be used for all sorts of things, from data analysis to web development. In this blog post, we'll show you how to use Python to work with the Keepa API to automate MySQL database ingestion. Keepa is a site that tracks Amazon prices and allows users to create price alerts. We'll walk you through the steps of setting up a Python environment and using the Keepa API to import data into your MySQL database. Let's get started!

Keepa product documentation for reference. Each of the endpoints for the API are defined in the documentation and used as the official documentation to support this script.

[Keepa](https://keepa.com/#!discuss/t/product-object/116)

Additional GitHub examples of working with the Keepa API that was used in reference to this script.

[GitHub - akaszynski/keepa: Python Keepa.com API](https://github.com/akaszynski/keepa)

The end product of this script are exports into each MySQL table as shown below.

![MySQL table output example](https://cdn.shopify.com/s/files/1/0411/4782/6343/files/MySQL_output_480x480.png?v=1651898004)

***Import Python Libraries needed for script.***

import pymysql
import keepa
import pandas as pd
import openpyxl
import datetime
from sqlalchemy import create_engine
import time

***Define your MySQL connection credentials to be used for your connection.***
\# Credentials to database connection
hostname=server name
dbname=database name
uname=username
pwd=password


***Create SQLAlchemy engine to connect to MySQL Database***
engine = create_engine("mysql+pymysql://{user}:{pw}@{host}/{db}"
.format(host=hostname, db=dbname, user=uname, pw=pwd))

mycursor = mydb.cursor()

accesskey = ***# enter real access key here***
api = keepa.Keepa(accesskey)

ASIN= *your array of ASINS to pass to Keepa*

***Single ASIN query***
products = api.query(ASIN,offers=100) # returns list of product data

***Access new price history and associated time data***


for i in range(len(ASIN)):
newprice = products[i]['data']['LISTPRICE']
newpricetime = products[i]['data']['LISTPRICE_time']
csv_NEW = products[i]['csv'][1]
csv_SALES = products[i]['csv'][3]
csv_RATING = products[i]['csv'][16]
csv_COUNT_REVIEWS = products[i]['csv'][17]
\#categories = products[i]['categories']
\#imagesCSV = products[i]['imagesCSV']
\#manufacturer = products[i]['manufacturer']
\#title = products[i]['title']
\#lastUpdate = products[i]['lastUpdate']
\#lastPriceChange = products[i]['lastPriceChange']
\#rootCategory = products[i]['rootCategory']
\#productType = products[i]['productType']
\#parentAsin = products[i]['parentAsin']
\#variationCSV = products[i]['variationCSV']
asin = products[i]['asin']
\#domainId= products[i]['domainId']
\#type= products[i]['type']
\#hasReviews= products[i]['hasReviews']
\#trackingSince= products[i]['trackingSince']
\#brand= products[i]['brand']
\#productGroup= products[i]['productGroup']
\#partNumber= products[i]['partNumber']
\#model = products[i]['model']
\#color= products[i]['color']
\#size= products[i]['size']
\#edition= products[i]['edition']
\#format= products[i]['format']
\#packageHeight= products[i]['packageHeight']
\#packageLength= products[i]['packageLength']
\#packageWidth= products[i]['packageWidth']
\#packageWeight= products[i]['packageWeight']
\#packageQuantity= products[i]['packageQuantity']
\#isAdultProduct= products[i]['isAdultProduct']
\#isEligibleForTradeIn= products[i]['isEligibleForTradeIn']
\#isEligibleForSuperSaverShipping= products[i]['isEligibleForSuperSaverShipping']
\#offers= products[i]['offers']
\#buyBoxSellerIdHistory= products[i]['buyBoxSellerIdHistory']
\#isRedirectASIN= products[i]['isRedirectASIN']
\#isSNS= products[i]['isSNS']
\#author= products[i]['author']
\#binding= products[i]['binding']
\#numberOfItems= products[i]['numberOfItems']
\#numberOfPages= products[i]['numberOfPages']
\#publicationDate= products[i]['publicationDate']
\#releaseDate= products[i]['releaseDate']
\#languages= products[i]['languages']
\#lastRatingUpdate= products[i]['lastRatingUpdate']
\#ebayListingIds= products[i]['ebayListingIds']
\#lastEbayUpdate= products[i]['lastEbayUpdate']
\#eanList= products[i]['eanList']
\#upcList= products[i]['upcList']
\#liveOffersOrder= products[i]['liveOffersOrder']
\#frequentlyBoughtTogether= products[i]['frequentlyBoughtTogether']
\#features= products[i]['features']
\#description= products[i]['description']
\#promotions= products[i]['promotions']
\#newPriceIsMAP= products[i]['newPriceIsMAP']
csv_coupon= products[i]['coupon']
\#availabilityAmazon= products[i]['availabilityAmazon']
csv_listedSince= products[i]['listedSince']
\#fbaFees= products[i]['fbaFees']
\#variations= products[i]['variations']
\#itemHeight= products[i]['itemHeight']
\#itemLength= products[i]['itemLength']
\#itemWidth= products[i]['itemWidth']
\#itemWeight= products[i]['itemWeight']
\#salesRankReference= products[i]['salesRankReference']
csv_salesRanks= products[i]['salesRanks']
\#salesRankReferenceHistory= products[i]['salesRankReferenceHistory']
\#launchpad= products[i]['launchpad']
\#isB2B= products[i]['isB2B']
\#stats= products[i]['stats']
\#offersSuccessful= products[i]['offersSuccessful']
\#g= products[i]['g']
\#categoryTree= products[i]['categoryTree']

***Can be plotted with matplotlib using:***
import matplotlib.pyplot as plt
plt.step(newpricetime, newprice, where='pre')

data = {'newprice':newprice, 'newpricetime':newpricetime}

***Use pandas to define data frames.***
df = pd.DataFrame(data, columns = ['newprice', 'newpricetime'])

csv_NEW = {'asin':asin,'csv_NEW': csv_NEW}
csv_SALES = {'asin':asin,'csv_SALES': csv_SALES}
csv_RATING = {'asin':asin,'csv_RATING': csv_RATING}
csv_COUNT_REVIEWS = {'asin':asin,'csv_COUNT_REVIEWS': csv_COUNT_REVIEWS}
\#trackingSince = {'trackingSince': trackingSince}
\#partNumber = {'partNumber': partNumber}
\#model = {'model': model}
\#frequentlyBoughtTogether = {'frequentlyBoughtTogether':frequentlyBoughtTogether}
coupon = {'asin':asin,'csv_coupon':csv_coupon}
\#fbaFees ={'fbaFees': fbaFees}
\#salesRankReference = {'salesRankReference':csv_salesRankReference}
salesRanks = {'asin':asin,'csv_salesRanks':csv_salesRanks}
listedSince = {'asin':asin,'csv_listedSince':csv_listedSince}
asins = {'ASIN':asin}

df_csv_NEW = pd.DataFrame(csv_NEW, columns = ['csv_NEW'])
df_csv_NEW1 = pd.DataFrame({'asin':asin,'date':df_csv_NEW['csv_NEW'].iloc[::2].values, 'value':df_csv_NEW['csv_NEW'].iloc[1::2].values})
\#df_csv_NEW1['ASIN'] = pd.Series([ASIN for x in range(len(df_csv_NEW1.index))])
\##df_csv_NEW1['date'] = (df_csv_NEW1['date'] + 21564000) * 60000
\##df_csv_NEW1['date'] = pd.to_datetime(df_csv_NEW1['date'], format='%Y%m%d %H:%M')

\#df_csv_COUPON = pd.DataFrame(coupon, columns = ['asin','csv_coupon'], index=[0])
\#df_csv_COUPON['ASIN'] = pd.Series([asins for x in range(len(df_csv_COUPON.index))])

df_csv_ListedSince = pd.DataFrame(listedSince, columns = ['asin','csv_listedSince'], index=[0])
\#df_csv_ListedSince['ASIN'] = pd.Series([asins for x in range(len(df_csv_ListedSince.index))])

df_csv_salesRanks = pd.DataFrame(salesRanks, columns = ['asin','csv_salesRanks'])
\#df_csv_salesRanks['ASIN'] = pd.Series([asins for x in range(len(df_csv_salesRanks.index))])

\#for column in df_csv_NEW1:
\#print((df_csv_NEW1['date'].values))

df_csv_SALES = pd.DataFrame(csv_SALES, columns = ['asin','csv_SALES'])
df_csv_SALES1 = pd.DataFrame({'asin':asin,'date':df_csv_SALES['csv_SALES'].iloc[::2].values, 'value':df_csv_SALES['csv_SALES'].iloc[1::2].values})
\#df_csv_SALES1['ASIN'] = pd.Series([asins for x in range(len(df_csv_SALES1.index))])

df_csv_RATING = pd.DataFrame(csv_RATING, columns = ['asin','csv_RATING'])
df_csv_RATING1 = pd.DataFrame({'asin':asin,'date':df_csv_RATING['csv_RATING'].iloc[::2].values, 'value':df_csv_RATING['csv_RATING'].iloc[1::2].values})
\#df_csv_RATING1['ASIN'] = pd.Series([asins for x in range(len(df_csv_RATING1.index))])

df_csv_COUNT_REVIEWS = pd.DataFrame(csv_COUNT_REVIEWS, columns = ['asin','csv_COUNT_REVIEWS'])
df_csv_COUNT_REVIEWS1 = pd.DataFrame({'asin':asin,'date':df_csv_COUNT_REVIEWS['csv_COUNT_REVIEWS'].iloc[::2].values, 'value':df_csv_COUNT_REVIEWS['csv_COUNT_REVIEWS'].iloc[1::2].values})
\#df_csv_COUNT_REVIEWS1['ASIN'] = pd.Series([asins for x in range(len(df_csv_COUNT_REVIEWS1.index))])

\#df_trackingSince = pd.DataFrame(trackingSince, columns = ['trackingSince'])
\#df_partNumber = pd.DataFrame(partNumber, columns = ['partNumber'])
\#df_model = pd.DataFrame(model, columns = ['model'])
\#df_frequentlyBoughtTogether = pd.DataFrame(frequentlyBoughtTogether, columns = ['frequentlyBoughtTogether'])
\#df_coupon = pd.DataFrame(coupon, columns = ['coupon'])
\#df_fbaFees = pd.DataFrame(fbaFees, columns = ['fbaFees'])
\#df_salesRankReference = pd.DataFrame(salesRankReference, columns = ['salesRankReference'])
\#df_salesRanks = pd.DataFrame(salesRanks, columns = ['salesRanks'])

***Write data frames to your local machine as Excel files.***
\#df_csv_NEW1.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\csv_NEW.xlsx",index=False)
\#df_csv_SALES1.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\csv_SALES.xlsx",index=False)
\#df_csv_RATING1.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\csv_RATING.xlsx",index=False)
\#df_csv_COUNT_REVIEWS1.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\csv_COUNT_REVIEWS.xlsx",index=False)
\#df_csv_COUPON.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\csv_COUPON.xlsx")
\#df_csv_ListedSince.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\csv_ListedSince.xlsx",index=False)
\#df_csv_salesRanks.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\csv_salesRanks.xlsx",index=False)
\#df_trackingSince.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\trackingSince.xlsx")
\#df_partNumber.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\partNumber.xlsx")
\#df_model.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\model.xlsx")
\#df_frequentlyBoughtTogether.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\frequentlyBoughtTogether.xlsx")
\#df_coupon.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\coupon.xlsx")
\#df_fbaFees.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\fbaFees.xlsx")
\#df_salesRankReference.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\salesRankReference.xlsx")
\#df_salesRanks.to_excel(r"C:\Users\prati\OneDrive\Documents\GWA Distribution Group\salesRanks.xlsx")

***In loop time delay.***

time.sleep(60)

***Insert whole Data Frame into each MySQL table.***
df_csv_NEW1.to_sql('keepa_price', engine, if_exists = 'append', chunksize = 1000)
df_csv_SALES1.to_sql('keepa_sales', engine, if_exists = 'append', chunksize = 1000)
df_csv_RATING1.to_sql('keepa_rating', engine, if_exists = 'append', chunksize = 1000)
df_csv_COUNT_REVIEWS1.to_sql('keepa_reviews', engine, if_exists = 'append', chunksize = 1000)
df_csv_ListedSince.to_sql('keepa_listedSince', engine, if_exists = 'append', chunksize = 1000)
\#df_csv_salesRanks.to_sql('keepa_salesRanks', engine, if_exists = 'append', chunksize = 1000)

mydb.commit()

print(mycursor.rowcount, "record(s) inserted.")


\#print(ASINS)
\#print(df)
\#print(df_csv_NEW1)
\#print( df_csv_SALES1)
\#print(df_csv_RATING1)
\#print(df_csv_COUNT_REVIEWS1)
\#print(df_csv_ListedSince)
\#print(df_csv_salesRanks)
\#print(i)
\# Keys can be listed by
\#print(products[i]['partNumber'])

\#print data
\#print(products[i])

\# Plot result (requires matplotlib)
\#keepa.plot_product(products[i])