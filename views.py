from flask import Flask, render_template, request
from flask import send_file
from sqlalchemy import desc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import io
from datetime import datetime
import pickle
import numpy as np
import pandas as pd

from jinja2 import FileSystemLoader

# コンペ特有のクラスを動的に選択して読み込むのは不可？？？
from competitions.news_click_prediction.ScoreCalculator import ScoreCalculator
from competitions.news_click_prediction.models import ScoreStore, SubmitStore

# 今後コンペも動的に選択できるようにしたい（動的ルーティングとかできるはず）
DEFAULT_COMPETITION = "news_click_prediction"

app = Flask(__name__)
app.config["DEBUG"] = True
# templatesディレクトリ以外からもマクロを指定したいので、jinja2が検索するパスを追加
app.jinja_loader = FileSystemLoader(["./templates", "./competitions"])

@app.route("/")
def top_page():
    db = load_db()
    return render_template("leaderboard.html", tables=db)

@app.route("/overview")
def overview_page():
    return render_template("overview.html", macro_src="./" + DEFAULT_COMPETITION + "/macro.html")

@app.route("/data")
def data_page():
    return render_template("data.html", macro_src="./" + DEFAULT_COMPETITION + "/macro.html")

@app.route("/submit")
def submit_page():
    return render_template("submit.html")


@app.route("/mysubmission")
def mysub_page():
    db = load_db()
    return render_template("mysubmission.html", tables=db)


@app.route("/submitresult", methods=['POST'])
def submitresult():
    submit_title = request.form["submit_name"]
    user_name = request.form["user_name"]
    filestream = request.files["upload_file"]
    try:
        file_content = decode_file(filestream)
        df_submit = convert_dataframe(file_content)
        # calculate score
        scores = get_scores(df_submit)
    except (ValueError, UnicodeDecodeError):
        return "submited file failed to convert data frame. please check. <a href='/submit'>back</a>"

    # ばかすかセッション作ってるの絶対良くないと思う
    engine = create_engine("sqlite:///competitions/" + DEFAULT_COMPETITION + "/submission.db", echo=False)
    session = sessionmaker(bind=engine)()
    # add file contents and upload infomation into database
    add_submitdb(user_id=user_name, submit_title=submit_title, # 後々ユーザー名とIDを対応させる処理を入れないといけない
                 file_content=file_content, session=session)
    # add scores into database この状態だとsubmitdbとscoredbを紐づける情報が失われている。
    #print(scores)
    add_scoredb(title=submit_title, user_id=user_name, session=session, **scores)

    db = load_db()
    return render_template("submitresult.html", tables=db, score=scores["total_click"])


@app.route("/data_download", methods=['GET'])
def data_download():
    return send_file("competitions/" + DEFAULT_COMPETITION + "/data.zip", as_attachment=True, attachment_filename="data.zip", mimetype="application/zip") 

# 処理関数たち

def decode_file(filestream):
    file_content = filestream.read()
    file_utf_8 = file_content.decode("utf-8")
    
    return file_utf_8.strip()

def convert_dataframe(file_content):
    df_submit = pd.read_csv(io.StringIO(file_content), header=0, delimiter="\t")

    # そもそもの提出ファイルのサイズチェック
    if df_submit.shape != (10000, 4):
        raise ValueError("Input size may be wrong. please check your file.")
    return df_submit

def get_scores(df_submit):
    # テキストからスコアを計算する
    sc = ScoreCalculator("./competitions/" + DEFAULT_COMPETITION + "/true_answer_v2.pkl")
    scores = sc.calc_score(df_submit)
    return scores

# データベース周りの関数たち
def add_submitdb(user_id, submit_title, file_content, session):
    # 提出ファイルのrow_textをデータベースに保存する
    nowtime = datetime.now()
    c2 = SubmitStore(user_id=user_id, title=submit_title, 
                     upload_date=nowtime, raw_text=file_content
                    )
    session.add(c2)
    session.commit()

def add_scoredb(title, user_id, session, total_click, auc, logloss, accuracy, pred_click):
    # スコアをデータベースに保存する
    diff = round(pred_click - total_click, 2)

    c = ScoreStore(title=title, user_id=user_id, 
                   total_click=total_click, auc=auc, logloss=logloss, 
                   accuracy=accuracy, pred_click=pred_click, diff=diff)
    session.add(c)
    session.commit()

def load_db():
    #return ScoreStore.query.order_by(desc(ScoreStore.total_click))
    engine = create_engine('sqlite:///competitions/' + DEFAULT_COMPETITION + '/submission.db', echo=False)

    session = sessionmaker(bind=engine)()

    tbl_score = pd.read_sql_query("SELECT * FROM score ORDER BY total_click", engine)
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

    return tbl_merged.sort_values("total_click", ascending=False)

# main routine
if __name__ == '__main__':
    port = 55522
    app.run(host="0.0.0.0", port=port)
    
