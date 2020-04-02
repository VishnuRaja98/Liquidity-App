from flask import Flask, request, redirect,url_for, render_template, session
from flask_mysqldb import MySQL
import csv
import os
from pandas import datetime, DataFrame
from sklearn.metrics import mean_squared_error
from statsmodels.tsa.arima_model import ARIMA

app=Flask(__name__)
app.secret_key='any_random_string'

app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root123'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_DB'] = 'liquiditydatabase'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

def add_months(curr_month, adder):
    year, month, day = curr_month.split('-')
    years_added = int(adder/12)
    months_added = adder%12
    year = str(int(year)+years_added)
    newmonth = int(month) + months_added
    if newmonth>12:
        year = str(int(year)+1)
        newmonth = newmonth - 12
        if newmonth<10:
            month = '0'+str(newmonth)
        else:
            month = str(newmonth)
    else:
        if newmonth<10:
            month = '0'+str(newmonth)
        else:
            month = str(newmonth)
    nextmonth = nextmonth = year+"-"+month+"-"+day
    return nextmonth

def next_month(curr_month):
    year, month, day = curr_month.split('-')
    if int(month)==12:
        month="01"
        year=str(int(year)+1)
    else:
        if int(month)<9:
            month="0"+str(int(month)+1)
        else:
            month=str(int(month)+1)
    nextmonth = year+"-"+month+"-"+day
    print("Now in month - "+nextmonth)
    return nextmonth
def emi_calc(principle,rate,time):
    r=rate/1200
    return round(principle*r*(1+r)**time/(((1+r)**time)-1),2)

def predictor_test():
    X = [266.0,145.9,183.1,119.3,180.3,168.5,231.8,224.5,192.8,122.9,336.5,185.9,194.3,149.5,210.1,273.3,191.4,287.0,226.0,303.6,289.9,421.6,264.5,342.3,339.7,440.4,315.9,439.3,401.3,437.4,575.5,407.6,682.0,475.3,581.3,646.9]
    size = int(len(X)*0.66)
    train, test = X[0:size], X[size:len(X)]
    history = [x for x in train]
    predictions = list()
    for t in range(len(test)):
        model = ARIMA(history,order=(6,2,0))
        model_fit = model.fit(disp=0)
        output = model_fit.forecast()
        yhat = output[0]
        print(output)
        predictions.append(yhat)
        obs = test[t]
        history.append(yhat)
        print('predicted=%f, expected=%f' % (yhat, obs))
    error = mean_squared_error(test,predictions)
    print('Test MSE: %.3f' % error)
    return str(predictions)

def readFile(month,cur):
    basedir = os.path.abspath(os.path.dirname(__file__))
    datafile = os.path.join(basedir, "static/loans"+month+".csv")
    with open(datafile,'r') as file:
        reader = csv.reader(file)
        for row in reader:
            amount = float(row[1])
            period = int(row[2])
            rate = float(row[3])
            emi = float(row[6])
            cur.callproc('spLendloan',[amount,period,rate,emi,month])
            mysql.connection.commit()
        print(month+" transactions complete")
    return

def setPastAndPredictions(data):
    query1 = "select lcr, cr from bank_vectors"
    cur = mysql.connection.cursor()
    cur.execute(query1)
    results1 = cur.fetchall()
    if len(results1)!=0:
        for result1 in results1:
            data["lcrpast"].append(result1["lcr"])
            data["crpast"].append(result1["cr"])
    #for predictions setup the model first
    return data
    
@app.route("/")
def index():
    #print(add_months('2007-06-01',50))
    #tempstr=predictor_test()
    #readFile("2007-06-01")
    #return "%s" %tempstr
    return render_template("login.html", error_message="")

@app.route("/login",methods=['POST','GET'])
def login():
    if request.method == "POST":
        uname=str(request.form['login_username'])
        pwd=str(request.form['login_password'])
        cur = mysql.connection.cursor()
        query_login = "SELECT * FROM users WHERE username='"+uname+"'"
        cur.execute(query_login)
        results = cur.fetchall()
        if len(results)==0:
            return render_template("login.html", error_message="wrong username")
        else:
            if pwd == results[0]['password']:
                #return render_template("home.html", dict={'array':[1,2,3],'secondarray':[9,8,7],'newdict':{'username':"uname",'password':"pwd"}})
                data={'user':results[0],"lcrpredictions":[],"crpredictions":[],"lcrpast":[],"crpast":[],"recommended_borrow":0}
                query_balance_sheet = "SELECT * FROM curr_bank_vector"
                cur.execute(query_balance_sheet)
                results=cur.fetchall()
                print(results)
                data['bank_vector']=results[0]
                if data['bank_vector']['money']-data['bank_vector']['operational_charge'] < 0:
                    data['recommended_borrow'] = (data['bank_vector']['money']-data['bank_vector']['operational_charge'])*-1 + 10
                else:
                    data['recommended_borrow'] = 0
                session['data']=data
                return render_template("home.html", data=data)
            else:
                return render_template("login.html", error_message="wrong password")

@app.route("/getfromcsv", methods = ["POST"])
def get_data_from_csv():
    return 'Not working.....'

@app.route("/newtransaction", methods = ["POST"])
def new_transaction():
    data=session['data']
    return render_template("new_transaction.html", data=data)

@app.route("/lend", methods = ["POST"])
def lend():
    data = session["data"] 

    if request.form["submitlendbtn"] == "Lend":
        amount = float(request.form["lend_amount"])
        period = int(request.form["lend_period"])
        intrest = float(request.form["lend_intrest"])
        emi = emi_calc(amount,intrest,period)
        cur = mysql.connection.cursor()
        cur.callproc('spLendloan',[amount,period,intrest,emi,data['bank_vector']["date"]])
        mysql.connection.commit()
        new_balance_sheet_query = "SELECT * FROM curr_bank_vector"
        cur.execute(new_balance_sheet_query)
        new_balance_sheet = cur.fetchall()
        data['bank_vector']=new_balance_sheet[0]
        if (data['bank_vector']['money']-data['bank_vector']['operational_charge']) < 0:
            data['recommended_borrow'] = (data['bank_vector']['money']-data['bank_vector']['operational_charge'])*-1 + 10
        else:
            data['recommended_borrow'] = 0
        session["data"]=data
        return render_template("home.html", data=data)
        

    elif request.form["submitlendbtn"] == "Get from CSV":
        cur = mysql.connection.cursor()
        readFile(data["bank_vector"]["date"],cur)
        new_balance_sheet_query = "SELECT * FROM curr_bank_vector"
        cur.execute(new_balance_sheet_query)
        new_balance_sheet = cur.fetchall()
        data['bank_vector']=new_balance_sheet[0]
        if data['bank_vector']['money']-data['bank_vector']['operational_charge'] < 0:
            data['recommended_borrow'] = (data['bank_vector']['money']-data['bank_vector']['operational_charge'])*-1 + 10
        else:
            data['recommended_borrow'] = 0
        session["data"]=data
        return render_template("home.html", data=data)

    elif request.form["submitlendbtn"] == "Check":
        amount = float(request.form["lend_amount"])
        period = int(request.form["lend_period"])
        intrest = float(request.form["lend_intrest"])
        return '%s' % str(session["data"])
    
    return render_template("home.html", data=data)

@app.route("/borrow", methods = ["POST"])
def borrow():
    data = session["data"] 
    amount = float(request.form["borrowed_amount"])
    period = int(request.form["borrowed_period"])
    intrest = float(request.form["borrowed_intrest"])

    if request.form["submitborrowbtn"] == "Borrow":
        emi = emi_calc(amount,intrest,period)
        cur = mysql.connection.cursor()
        cur.callproc('spBorrowloan',[amount,period,intrest,emi,data['bank_vector']["date"]])
        mysql.connection.commit()
        new_balance_sheet_query = "SELECT * FROM curr_bank_vector"
        cur.execute(new_balance_sheet_query)
        new_balance_sheet = cur.fetchall()
        data['bank_vector']=new_balance_sheet[0]
        if data['bank_vector']['money']-data['bank_vector']['operational_charge'] < 0:
            data['recommended_borrow'] = (data['bank_vector']['money']-data['bank_vector']['operational_charge'])*-1 + 10
        else:
            data['recommended_borrow'] = 0
        session["data"]=data
        return render_template("home.html", data=data)
        

    elif request.form["submitborrowbtn"] == "Check":
        return '%s' % str(session["data"])
    
    return render_template("home.html", data=data)

@app.route("/nextmonth", methods = ["POST"])
def nextmonth():
    cur = mysql.connection.cursor()
    cur.callproc('spNextmonth',[next_month(session['data']['bank_vector']['date'])])
    mysql.connection.commit()
    query_balance_sheet = "SELECT * FROM curr_bank_vector"
    data = session["data"]
    cur.execute(query_balance_sheet)
    results=cur.fetchall()
    print(results)
    data['bank_vector']=results[0]
    if data['bank_vector']['money']-data['bank_vector']['operational_charge'] < 0:
        data['recommended_borrow'] = (data['bank_vector']['money']-data['bank_vector']['operational_charge'])*-1 + 10
    else:
        data['recommended_borrow'] = 0
    session['data']=data
    return render_template("home.html", data = data)

@app.route("/resetEverything", methods = ["POST"])
def resetEverything():
    cur = mysql.connection.cursor()
    cur.callproc('spReset')
    mysql.connection.commit()
    query_balance_sheet = "SELECT * FROM curr_bank_vector"
    data = session["data"]
    cur.execute(query_balance_sheet)
    results=cur.fetchall()
    print(results)
    data['bank_vector']=results[0]
    if data['bank_vector']['money']-data['bank_vector']['operational_charge'] < 0:
        data['recommended_borrow'] = (data['bank_vector']['money']-data['bank_vector']['operational_charge'])*-1 + 10 #10 is operational_Charge increment with each borrow
    else:
        data['recommended_borrow'] = 0
    session['data']=data
    return render_template("home.html", data = data)


if __name__ == '__main__':
	app.run(debug = True)