"""
train.py
训练模块
"""
import os
import random
import numpy
import click
import gc
from scipy.sparse import lil_matrix, coo_matrix
from tqdm import tqdm
from datetime import datetime
import pickle


class Model:
    def __init__(self, word_set, Pspam, Pham, PS, PH, created_at):
        self.word_set = word_set
        self.Pspam = Pspam
        self.Pham = Pham
        self.PS = PS
        self.PH = PH
        self.created_at: datetime = created_at


def load_dataset(data_dir, ratio=1.0, dataset_pickle_filepath=''):
    """
    读取数据集，随机打乱
    :param data_dir:                经过 preprocess.py 处理过的输出目录路径
    :param ratio:                   读取百分比
    :param dataset_pickle_filepath: 数据集 pickle 文件路径，留空则不会生成/读取
    :return dataset:                示例 [(1, ['哈哈', '呵呵'])...]，1 代表 spam 0 代表 ham
    """
    dataset = list()
    # 可选使用 pickle 文件加快数据集读取速度
    if len(dataset_pickle_filepath) != 0 and os.path.exists(dataset_pickle_filepath):
        print('发现数据集 pickle 文件')
        with open(dataset_pickle_filepath, 'rb') as f:
            dataset = pickle.load(f)
    else:
        labels = os.listdir(data_dir)
        for label in labels:
            label_dir = os.path.join(data_dir, label)
            filenames = os.listdir(label_dir)
            print('开始读取{}'.format(label))
            # CLI 进度条
            pbar = tqdm(total=len(filenames))
            # 进度条计数，满 100 更新一次进度条
            pcount = 0
            for filename in filenames:
                file_path = os.path.join(label_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw_text = f.read()
                words = raw_text.split(',')
                dataset.append((1 if label == 'spam' else 0, words))
                pcount += 1
                if pcount == 100:
                    pbar.update(pcount)
                    pcount = 0
            pbar.update(pcount)
            pbar.close()
        if len(dataset_pickle_filepath) != 0:
            with open(dataset_pickle_filepath, 'wb') as f:
                pickle.dump(dataset, f)
                print('生成 pickle 文件成功：', dataset_pickle_filepath)
    random.shuffle(dataset)
    dataset = dataset[:int(len(dataset) * ratio)]
    return dataset


def create_word_set(dataset):
    """
    创建不含重复词的词集
    :param dataset:
    :return:
    """
    word_set = set()
    for label, words in dataset:
        word_set |= set(words)
    return list(word_set)


def words2vector(word_set, words, word_dict=None):
    if word_dict is None:
        word_dict = {word: i for i, word in enumerate(word_set)}
    vector = numpy.zeros(len(word_set), dtype=numpy.uint8)
    for word in words:
        if word in word_set:
            vector[word_dict[word]] = 1
    return vector


def dataset2vectors(word_set, dataset):
    """
    将数据集转化为词向量
    :param word_set: 由 create_word_set 得到的不含重复词的词集
    :param dataset:  数据集
    :return:
        vectors:
        labels:
    """
    # word_dict 的对应关系为 词 -> 该词的位置
    word_dict = {word: i for i, word in enumerate(word_set)}
    gc.collect()
    # vector 的总数（vectors 的长度）等于邮件集的数量
    # vector 的长度为词集的长度
    # vector 的元素值有两种：1 代表词集中该位置的词在本邮件中出现了，0 则相反
    # 使用稀疏矩阵解决内存不足的问题
    vectors = lil_matrix((len(dataset), len(word_set)), dtype=numpy.uint8)
    # vectors = numpy.zeros((len(dataset), len(word_set)), dtype='float64')
    # labels 的长度为邮件集的数量
    # labels 的元素值有两种：1 代表该位置的邮件为垃圾邮件，0 则为正常邮件
    labels = numpy.zeros(len(dataset), dtype=numpy.uint8)
    # CLI 进度条
    pbar = tqdm(total=len(dataset))
    # 进度条计数，满 100 更新一次进度条
    pcount = 0
    for i, (label, words) in enumerate(dataset):
        for word in words:
            if word in word_dict:
                vectors[i, word_dict[word]] = 1
        labels[i] = label
        pcount += 1
        if pcount == 100:
            pbar.update(pcount)
            pcount = 0
    pbar.update(pcount)
    pbar.close()
    return vectors, labels


def train_nb(vectors, labels, word_set=None):
    """
    训练模型
    :param vectors:
    :param labels:
    :return:
        Pspam: P(是垃圾邮件)
        Pham:  P(是正常邮件)
        PS: P(是垃圾邮件|出现该词) 的矩阵
        PH: P(是正常邮件|出现该词) 的矩阵
    """
    Pspam = sum(labels) / labels.shape[0]  # 垃圾邮件概率
    Pham = 1 - Pspam  # 非垃圾邮件概率
    gc.collect()
    # 这里要用拉普拉斯平滑
    SN = numpy.ones(vectors.shape[1], dtype=numpy.float64)
    HN = numpy.ones(vectors.shape[1], dtype=numpy.float64)
    coo_vectors = coo_matrix(vectors)
    # CLI 进度条
    pbar = tqdm(total=sum(coo_vectors.data))
    # 进度条计数，满 100 更新一次进度条
    pcount = 0
    for i, j, v in zip(coo_vectors.row, coo_vectors.col, coo_vectors.data):
        # 如果是垃圾邮件
        if labels[i] == 1:
            SN[j] += v
        else:
            HN[j] += v
        pcount += 1
        if pcount == 100:
            pbar.update(pcount)
            pcount = 0
    pbar.update(pcount)
    pbar.close()
    PS = SN / sum(SN)
    PH = HN / sum(HN)
    return Pspam, Pham, PS, PH


def predict_nb(vectors, Pspam, Pham, PS, PH, show_progress_bar=True):
    """
    判断垃圾/正常邮件
    :param vectors:         需要判断的邮件集的词向量矩阵
    :param Pspam:           P(是垃圾邮件)
    :param Pham:            P(是正常邮件)
    :param PS:              P(是垃圾邮件|出现该词) 的矩阵
    :param PH:              P(是正常邮件|出现该词) 的矩阵
    :return predict_vector: 预测结果矩阵，1 代表该位置的邮件为垃圾邮件，0 则正常
    """
    # log 防止小数溢出
    Pspam, Pham = numpy.math.log(Pspam), numpy.math.log(Pham)
    PS, PH = numpy.log(PS), numpy.log(PH)
    predict_vector = numpy.zeros(vectors.shape[0], dtype=numpy.uint8)
    probalities = list()
    if show_progress_bar:
        # CLI 进度条
        pbar = tqdm(total=vectors.shape[0])
        # 进度条计数，满 100 更新一次进度条
        pcount = 0
    for i, vector in enumerate(vectors):
        pspam = Pspam + sum(vector * PS)
        pham = Pham + sum(vector * PH)
        if pspam > pham:
            predict_vector[i] = 1
        if show_progress_bar:
            pcount += 1
            if pcount == 100:
                pbar.update(pcount)
                pcount = 0
        probalities.append((pspam, pham))
    if show_progress_bar:
        pbar.update(pcount)
        pbar.close()
    # predict_vector = [1 if (Pspam + sum(vector * PS)) >= (Pham + sum(vector * PH)) else 0 for vector in vectors]
    return predict_vector, probalities


def split_vectors_by_ratio(vectors, labels, train_size, test_size):
    """
    按照一定的比例切分向量
    :param vectors:
    :param labels:
    :param train_size:   训练集大小
    :param test_size:   测试集大小
    :return:
    """
    train_num = int(vectors.shape[0] * train_size)
    train_vectors = vectors[:train_size]
    train_labels = labels[:train_size]
    test_vectors = vectors[train_size:train_size + test_size]
    test_labels = labels[train_size:train_size + test_size]
    return train_vectors, train_labels, test_vectors, test_labels


def calc_accuracy(predicts, labels):
    """
    计算准确率
    :param predicts:
    :param labels:
    :return:
    """
    return numpy.mean(predicts == labels)


def calc_precision(predicts, labels):
    """
    计算精确率
    :param predicts:
    :param labels:
    :return:
    """
    tp = 0
    for i in range(predicts.shape[0]):
        if predicts[i] == labels[i] == 1:
            tp += 1
    return tp / sum(predicts)


def calc_recall(predicts, labels):
    """
    计算召回率
    :param predicts:
    :param labels:
    :return:
    """
    tp = 0
    for i in range(predicts.shape[0]):
        if predicts[i] == labels[i] == 1:
            tp += 1
    return tp / sum(labels)


def run(train_size, test_size, dataset_pickle_filepath, output_pickle_filepath):
    dataset = load_dataset('./data', 1, dataset_pickle_filepath)
    dataset = dataset[:train_size + test_size]
    train_dataset = dataset[:train_size]
    test_dataset = dataset[train_size:]
    print('数据集读取成功，总数 {}'.format(len(dataset)))
    word_set = create_word_set(train_dataset)
    print('词集创建成功，长度', len(word_set), '，开始创建词向量')
    train_vectors, train_labels = dataset2vectors(word_set, train_dataset)
    test_vectors, test_labels = dataset2vectors(word_set, test_dataset)
    print('词向量创建成功')
    # train_vectors, train_labels, test_vectors, test_labels = split_vectors_by_ratio(vectors, labels, train_size, test_size)
    print('数据集切分成功，训练集长度 {}×{}，测试集长度 {}×{}'.format(train_vectors.shape[0], train_vectors.shape[1],
                                                   test_vectors.shape[0], test_vectors.shape[1]))
    print('开始训练，训练集长度 {}×{}'.format(train_vectors.shape[0], train_vectors.shape[1]))
    Pspam, Pham, PS, PH = train_nb(train_vectors, train_labels, word_set)
    print('开始测试，测试集长度 {}×{}'.format(test_vectors.shape[0], test_vectors.shape[1]))
    predict_vector, probabilities = predict_nb(test_vectors, Pspam, Pham, PS, PH)
    accuracy = calc_accuracy(predict_vector, test_labels)
    precision = calc_precision(predict_vector, test_labels)
    recall = calc_recall(predict_vector, test_labels)
    print('测试完成，准确率 {}，精确率 {}，召回率 {}%'.format(accuracy, precision, recall))

    # 防止 __main__.Model 问题
    # https://stackoverflow.com/questions/40287657/load-pickled-object-in-different-file-attribute-error
    from train import Model
    output = Model(word_set, Pspam, Pham, PS, PH, datetime.now())
    with open(output_pickle_filepath, 'wb') as f:
        pickle.dump(output, f)
    return word_set, accuracy, precision, recall


@click.command()
@click.option('-t', 'train_size', default=40000, help='训练集集大小，default 40000')
@click.option('-T', 'test_size', default=20000, help='测试集大小, default 20000')
@click.option('-d', 'dataset_pickle_filepath', default='',
              help='dataset pickle 文件路径，程序在读取数据集时会自动生成/读取 pickle 文件以加快读取速度，default \'\'')
@click.option('-o', 'output_pickle_filepath', default='model.pickle',
              help='输出 pickle 路径，{word_set, Pspam, Pham, PS, PH}, default \'model.pickle\'')
# @click.option('-f', 'float_precision', default=16, help='浮点数精度，available16 32 64，default 16')
def main(train_size, test_size, dataset_pickle_filepath, output_pickle_filepath):
    run(train_size, test_size, dataset_pickle_filepath, output_pickle_filepath)


if __name__ == '__main__':
    main()
