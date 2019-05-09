# nb_spam 基于朴素贝叶斯的垃圾邮件过滤（识别）

## 准备工作
- 解压数据集：`tar xvf trec06c.tgz`


## 运行

### 提前分词
```shell
# python preprocess.py --help
Usage: preprocess.py [OPTIONS]

Options:
  -t TEXT     trec06 数据集根路径，default ./trec06c
  -s TEXT     禁用词表 GLOB，default ./stopwords/\*.txt
  -T TEXT     输出文件目标目录，default ./data
  -n INTEGER  消费者进程数，default 4
  --help      Show this message and exit.
```
例如：
```shell
python preprocess.py -t ./trec06c -s 'stopwords/\*.txt' -T ./data -n 6
```

### 运行训练集、测试集
```shell
# python predict.py --help                            
Usage: predict.py [OPTIONS]

Options:
  -r FLOAT  读取数据集比例，default 1.0
  -t FLOAT  训练集集比例，default 0.67
  -d TEXT   dataset pickle 文件路径，程序在读取数据集时会自动生成/读取 pickle 文件以加快读取速度，default ''
  --help    Show this message and exit.
```
例如：
```shell
python predict.py -r 1 -t 0.67 -d ./dataset.pickle
```