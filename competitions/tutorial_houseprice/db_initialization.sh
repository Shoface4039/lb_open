#!/usr/bin/bash

# 既存テーブルのバックアップ
if [ -e submission.db ]; then
  mkdir -p backup
  sqlite3 submission.db < make_backup.sql 
  rm submission.db
fi

# 新規作成
sqlite3 submission.db < create_table.sql


# staticディレクトリを参照できないので、ルートのstaticディレクトリにstatic以下をコピーする
mkdir ../../static/tutorial_houseprice
cp ./static/ ../../static/tutorial_houseprice/


# 上の処理を追加したため、もはやdb_initialization.shというファイル名は不適切。あとで直す
# 命名案：competition_initialization.sh ←もうこれでいっか
