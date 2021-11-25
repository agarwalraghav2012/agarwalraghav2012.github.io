# Store this code in 'app.py' file

from flask import Flask, render_template, request, redirect, url_for, session
# from flask_mysqldb import MySQL
# import MySQLdb.cursors
import re
from flask import Flask
from flask import request
from flask import render_template
from bokeh.embed import components
from bokeh.plotting import figure
import pandas as pd
import numpy as np
import math
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors
import matplotlib.pyplot as plt
import seaborn as sns
from bokeh.io import output_notebook
from bokeh.plotting import figure, show
from bokeh.io import output_file
from datetime import datetime, timedelta
import sqlite3 as sql
from flask import g

app = Flask(__name__)


app.secret_key = 'your secret key'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345'
app.config['MYSQL_DB'] = 'proj'

mysql = MySQL(app)

movies = pd.read_csv("archive/movies.csv", encoding = "latin")
ratings = pd.read_csv("archive/ratings.csv")
final_dataset = ratings.pivot(index='movieId',columns='userId',values='rating')
final_dataset.fillna(0,inplace=True)

no_user_voted = ratings.groupby('movieId')['rating'].agg('count')
no_movies_voted = ratings.groupby('userId')['rating'].agg('count')
final_dataset = final_dataset.loc[no_user_voted[no_user_voted > 5].index,:]
final_dataset=final_dataset.loc[:,no_movies_voted[no_movies_voted > 5].index]

csr_data = csr_matrix(final_dataset.values)
final_dataset.reset_index(inplace=True)
knn = NearestNeighbors(metric='cosine', algorithm='brute', n_neighbors=20, n_jobs=-1)
knn.fit(csr_data)

def get_movie_recommendation(movie_name):
    n_movies_to_reccomend = 10
    movie_list = movies[movies['title'] == movie_name]  
    if len(movie_list):        
        movie_idx= movie_list.iloc[0]['movieId']
        movie_idx = final_dataset[final_dataset['movieId'] == movie_idx].index[0]
        distances , indices = knn.kneighbors(csr_data[movie_idx],n_neighbors=n_movies_to_reccomend+1)    
        rec_movie_indices = sorted(list(zip(indices.squeeze().tolist(),distances.squeeze().tolist())),key=lambda x: x[1])[:0:-1]
        recommend_frame = []
        for val in rec_movie_indices:
            movie_idx = final_dataset.iloc[val[0]]['movieId']
            idx = movies[movies['movieId'] == movie_idx].index
            recommend_frame.append({'Title':movies.iloc[idx]['title'].values[0],'Distance':val[1]})
        df = pd.DataFrame(recommend_frame,index=range(1,n_movies_to_reccomend+1))
        return df.sort_values(by=['Distance'],ascending=True, ignore_index=True)
    else:
        return "No movies found. Please check your input"

@app.route('/')
@app.route('/login', methods =['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = % s AND password = % s', (username, password, ))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            msg = 'Logged in successfully !'
            table = pd.read_csv('archive/movies.csv', encoding = "latin")
            movie_names = table.title.unique()
            return redirect(url_for('index'))
        else:
            msg = 'Incorrect username / password !'
    return render_template('login.html', msg = msg)
    # return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/index', methods =['GET','POST'])
def index():
        msg=''
        table = pd.read_csv('archive/movies.csv', encoding = "latin")
        movie_names = table.title.unique()
        # print(len(movie_names))
        # print(session)
        if request.method == 'GET' and bool(session) :
            username = session['username']
            cursor3 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            # cursor2.execute('INSERT INTO user_movie VALUES (NULL, % s, % s, % s)', (username, movie, rating, ))
            # mysql.connection.commit()
            cursor3.execute('SELECT * FROM user_movie WHERE username = %s', [username])
            watched_movie = cursor3.fetchall()
            le = len(watched_movie)
            sup_li = list()
            for mov in watched_movie:
                try:
                    li = get_movie_recommendation(mov['movie'])['Title']
                    sup_li.extend(li[0:math.ceil(10/le)])                          
                except IndexError :
                    pass            
            return render_template('index.html', movie_names=movie_names , watched_movie=watched_movie, movie_list=sup_li,)            
        if request.method == 'POST' and 'movie' in request.form:
                movie = request.form['movie']
                rating = request.form['rating']
                username = session['username']
                # print(session['username'])
                cursor2 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                try:
                    cursor2.execute('INSERT INTO user_movie VALUES (NULL, % s, % s, % s)', (username, movie, rating, ))
                    mysql.connection.commit()
                except Exception:
                    pass

                cursor2.execute('SELECT * FROM user_movie WHERE username = %s', [username])
                watched_movie = cursor2.fetchall()
                # print(watched_movie)
                # for mov in watched_movie :
                #   print(mov['username'])              
                try :
                    le = len(watched_movie)
                    sup_li = list()
                    for mov in watched_movie:
                        try:
                            li = get_movie_recommendation(mov['movie'])['Title']
                            sup_li.extend(li[0:math.ceil(10/le)])                          
                        except IndexError :
                            pass
                    # li = get_movie_recommendation(movie)['Title']
                    return render_template('index.html', movie_names=movie_names, movie_list=sup_li, watched_movie=watched_movie)
                except IndexError :
                        return render_template('index.html', watched_movie=watched_movie, movie_names=movie_names, er="Doesn't have enough ratings to recommend!")
        elif request.method == 'POST':
            username = session['username']
            cursor3 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            # cursor2.execute('INSERT INTO user_movie VALUES (NULL, % s, % s, % s)', (username, movie, rating, ))
            # mysql.connection.commit()
            cursor3.execute('SELECT * FROM user_movie WHERE username = %s', [username])
            watched_movie = cursor3.fetchall()
            return render_template('index.html', movie_names=movie_names , watched_movie=watched_movie)
        return render_template('login.html')
        
        
@app.route('/register', methods =['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form :
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE username = % s', (username, ))
        account = cursor.fetchone()
        if account:
            msg = 'Account already exists !'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address !'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers !'
        elif not username or not password or not email:
            msg = 'Please fill out the form !'
        else:
            cursor.execute('INSERT INTO accounts VALUES (NULL, % s, % s, % s)', (username, password, email, ))
            mysql.connection.commit()
            msg = 'You have successfully registered !'
    elif request.method == 'POST':
        msg = 'Please fill out the form !'
    return render_template('register.html', msg = msg)

@app.route('/new_movie',methods = ['GET','POST'])
def new_movie():
    # table = pd.read_csv('NIFTY50_all.csv')
    # stock_symbols = table.Symbol.unique()
    
    if request.method == 'GET':
        return render_template('new_movie.html')





if __name__ == "__main__" :
    app.run(debug=True)
