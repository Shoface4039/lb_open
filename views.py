from flask import Flask, render_template, request
from flask import send_file
from sqlalchemy import desc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import io, os
from datetime import datetime
import pickle
import numpy as np
import pandas as pd

from jinja2 import FileSystemLoader

# コンペ特有のクラスを動的に選択して読み込むのは不可？？？
# https://qiita.com/progrommer/items/abd2276f314792c359daにあるように、importlibを使ってできそう
#from competitions.news_click_prediction.ScoreCalculator import ScoreCalculator
#from competitions.news_click_prediction.models import ScoreStore, SubmitStore
import importlib


app = Flask(__name__)
app.config["DEBUG"] = True
# templatesディレクトリ以外からもマクロを指定したいので、jinja2が検索するパスを追加
app.jinja_loader = FileSystemLoader(["./templates", "./competitions"])

@app.route("/")
def top_page():
    # 暫定トップページ。competitions以下にある物全てにリンクを用意（ページがあるとは限らない）
    s = "".join(["<a href={0}/overview>competiton: {0}</a><br>".format(i) for i in os.listdir("./competitions")])
    return s

@app.route("/<compe>/")
@app.route("/<compe>/overview")
def overview_page(compe):
    return render_template("overview.html", macro_src="./" + compe + "/macro.html")

@app.route("/<compe>/data")
def data_page(compe):
    return render_template("data.html", macro_src="./" + compe + "/macro.html")

@app.route("/<compe>/leaderboard")
def leaderboard_page(compe):
    ScoreCalculator = importlib.import_module("competitions." + compe + ".ScoreCalculator")
    sc = ScoreCalculator.ScoreCalculator("./competitions/" + compe + "/true_answer.pkl")
    db = load_db(compe, sc.main_score, sc.disp_score, sc.ascending)
    return render_template("leaderboard.html", tables=db, compe=compe)

@app.route("/<compe>/submit")
def submit_page(compe):
    return render_template("submit.html", compe=compe)


@app.route("/<compe>/mysubmission")
def mysub_page(compe):
    ScoreCalculator = importlib.import_module("competitions." + compe + ".ScoreCalculator")
    sc = ScoreCalculator.ScoreCalculator("./competitions/" + compe + "/true_answer.pkl")
    db = load_db(compe, sc.main_score, sc.disp_score, sc.ascending)
    return render_template("mysubmission.html", tables=db, compe=compe)


@app.route("/<compe>/submitresult", methods=['POST'])
def submitresult(compe):
    # 例外の読み込み
    ScoreCalculator = importlib.import_module("competitions." + compe + ".ScoreCalculator")
    
    submit_title = request.form["submit_name"]
    user_name = request.form["user_name"]
    filestream = request.files["upload_file"]
    try:
        file_content = decode_file(filestream)
        df_submit = convert_dataframe(file_content)
        # calculate score
        sc, scores = get_scores(df_submit, compe)
    except (ValueError, UnicodeDecodeError):
        return "submited file failed to convert data frame. please check. <a href='/"+compe+"/submit'>back</a>"
    except ScoreCalculator.FileCheckError as e:
        return e.message + "\n <a href='/" + compe + "/submit'>back</a>"

    # ばかすかセッション作ってるの絶対良くないと思う
    engine = create_engine("sqlite:///competitions/" + compe + "/submission.db", echo=False)
    session = sessionmaker(bind=engine)()
    # add file contents and upload infomation into database
    add_submitdb(user_id=user_name, submit_title=submit_title, # 後々ユーザー名とIDを対応させる処理を入れないといけない
                 file_content=file_content, session=session, compe=compe)
    # add scores into database この状態だとsubmitdbとscoredbを紐づける情報が失われている。
    add_scoredb(title=submit_title, user_id=user_name, session=session, compe=compe,  **scores)

    db = load_db(compe, sc.main_score, sc.disp_score, sc.ascending)
    return render_template("submitresult.html", tables=db, main_score=scores[sc.main_score], compe=compe,
                           macro_src="./" + compe + "/macro.html")


@app.route("/<compe>/data_download", methods=['GET'])
def data_download(compe):
    return send_file("./competitions/" + compe + "/data.zip", 
                     as_attachment=True, 
                     attachment_filename="data.zip", 
                     mimetype="application/zip") 

# 処理関数たち
def decode_file(filestream):
    file_content = filestream.read()
    file_utf_8 = file_content.decode("utf-8")
    
    return file_utf_8.strip()

def convert_dataframe(file_content):
    df_submit = pd.read_csv(io.StringIO(file_content), header=0, delimiter="\t")

    return df_submit

def get_scores(df_submit, compe):
    # コンペ特有のスコア計算モジュールを読み込み
    ScoreCalculator = importlib.import_module("competitions." + compe + ".ScoreCalculator")
    # テキストからスコアを計算する
    sc = ScoreCalculator.ScoreCalculator("./competitions/" + compe + "/true_answer.pkl")
    scores = sc.calc_score(df_submit)
    return sc, scores

# データベース周りの関数たち
def add_submitdb(user_id, submit_title, file_content, session, compe):
    models = importlib.import_module("competitions." + compe + ".models")
    # 提出ファイルのrow_textをデータベースに保存する
    nowtime = datetime.now()
    c2 = models.SubmitStore(user_id=user_id, title=submit_title, 
                            upload_date=nowtime, raw_text=file_content
                           )
    session.add(c2)
    session.commit()

#def add_scoredb(title, user_id, session, compe, total_click, AUC, logloss, Accuracy, pred_click, diff):
def add_scoredb(title, user_id, session, compe, **args):
    models = importlib.import_module("competitions." + compe + ".models")
    # スコアをデータベースに保存する
    c = models.ScoreStore(title, user_id, **args)
    session.add(c)
    session.commit()

def load_db(compe, sort_column, display_column, sort_ascending):
    engine = create_engine('sqlite:///competitions/' + compe + '/submission.db', echo=False)

    session = sessionmaker(bind=engine)()

    tbl_score = pd.read_sql_query("SELECT * FROM score ORDER BY " + sort_column, engine)
    tbl_submit = pd.read_sql_query("SELECT * FROM submit", engine)
    
    tbl_merged = pd.merge(tbl_score, tbl_submit[["id", "upload_date"]], on="id", how="inner")
    
    # convert datetime into strings such as "XX month ago", or "XX minitues ago".
    def convert_time(t):
        time = datetime.strptime(t, "%Y-%m-%d %H:%M:%S.%f")
        diff = datetime.now() - time

        passed_list = [diff.days//30, diff.days, diff.seconds // 3600, diff.seconds // 60]

        accessory = ["mo", "d", "hr", "min"]

        passed = "now"
        for p, a in zip(passed_list, accessory):
            if p == 0: pass
            else:
                passed = "{}{}{}".format(p, a, "s" if a == "hr" and p > 1 else "")
                break

        return passed

    tbl_merged["upload_date"] = tbl_merged["upload_date"].map(convert_time)
    
    # generate entry count
    s = tbl_merged.groupby("user_id").agg({"id":"count"}).reset_index()
    tbl_merged = pd.merge(tbl_merged, s.rename({"id": "entry"}, axis=1), on="user_id", how="left")

    # leave top score each user
    #top_scores_index = np.ravel(tbl_merged.groupby("user_id").agg({"total_click": np.argmax}))
    #tbl_merged = tbl_merged.iloc[top_scores_index]

    # align columns order
    tbl_merged = tbl_merged[["title", "user_id", sort_column] + display_column + ["entry", "upload_date"]]

    return tbl_merged.sort_values(sort_column, ascending=sort_ascending)

# main routine
if __name__ == '__main__':
    port = 55522
    app.run(host="0.0.0.0", port=port)
    
