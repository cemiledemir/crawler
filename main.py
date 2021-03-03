# This is a sample Python script.
from pandas import DataFrame
import pandas as pd


def main():
    blocks = pd.read_csv("stopwords.csv")
    print(blocks)
    new = blocks["nnnnnnn"].values.tolist()
    print(new)
    # df.to_csv("stopwords.csv", index=False)


if __name__ == '__main__':
    main()