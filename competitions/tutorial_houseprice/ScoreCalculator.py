import pickle

import numpy as np
import pandas as pd
    

class ScoreCalculator():
    df_ans_data = None

    def __init__(self, path):
        self.main_score = "RMSLE"
        self.disp_score = []
        self.ascending = True
        with open(path, "rb") as f:
            self.df_ans_data = pickle.load(f)
    
    # 提出データが求める形式か調べる
    def _check_data(self, df):
        # データサイズが正しいか
        if df.shape != (292, 2):
            raise DataSizeError(df.shape)
        # 欠損値がないか
        if df.isna().any().any():
            raise NullContainsError(df.isna().sum().sum())
        # 列名が正しいか
        if any([c not in df.columns for c in ["Id", "SalePrice"]]):
            raise ColumnNameError()
        # データ型が正しいか
        correct_type = {"Id": [np.dtype("int")], "SalePrice": [np.dtype("int"),np.dtype("float")]}
        dic = {}
        for c in df.columns:
            if df[c].dtype not in correct_type[c]:
                dic[c] = df[c].dtype
        if len(dic) > 0:
            raise DataTypeError(dic)
        
        return 1

    # 正解データと提出データの紐付け
    def _merge_data(self, df, keys):
        df = pd.merge(self.df_ans_data, df, on=keys, how="inner") 
        
        # 結合できなかったデータがないか（列名は調べているからpd.mergeでエラーは出ないとの想定）
        if df.shape != (292, 3) or df["Id"].nunique() != 292:
            raise DataUnMergedError("データの結合に失敗しました。Idなどをチェックして下さい。")
        
        return df

    # 評価指標の定義
    def _calc_rmsle(self, actual, predicted):
        msle = ((np.log(t+1) - np.log(p+1))**2).sum()/len(t)
        rmsle = msle ** 1/2
        return rmsle
    
    
    # 実際に使うメソッド
    def calc_score(self, df_submit_data):
        # データのサイズ等確認
        self._check_data(df_submit_data)
        
        # データ整形
        df_merged = self._merge_data(df_submit_data, keys=["Id"])

        # 評価指標の算出
        actual = df_merged["TruePrice"].values
        predict = df_merged["SalePrice"].values

        rmlse = self._calc_rmsle(actual, predict)
        
        scores = {"RMLSE": round(rmlse, 4)}
 
        return scores   
    
# 独自定義例外
class FileCheckError(Exception):
    " 提出ファイルが正しいかどうかのチェックポイントに関する基底エラー "
    pass
    
class DataSizeError(FileCheckError):
    # 望ましいデータサイズは、(292, 2)
    def __init__(self, data_size):
        self.message = "望ましいデータサイズは(292, 2)ですが、あなたが提出したデータのサイズは{}です。".format(data_size)

class NullContainsError(FileCheckError):
    # データに一つでも欠損値が入っていたらエラー
    def __init__(self, NA_count):
        self.message = "あなたが提出したデータには欠損値が{}個入っていました。".format(NA_count)
    
class ColumnNameError(FileCheckError):
    # 列名が間違っていないか
    def __init__(self):
        self.message = "あなたが提出したデータの列名が間違っています。"
    
class DataTypeError(FileCheckError):
    # 各列のデータ型を調べる
    def __init__(self, type_dict):
        self.message = "あなたが提出したデータは、"
        
        for k, v in type_dict.items():
            self.message += "\n{}の型が{}になっています。".format(k,v)
    
class DataUnMergedError(FileCheckError):
    def __init__(self, message):
        self.message = message
