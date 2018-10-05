import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os
import time

from aOTTtfVariable import aOTTtfVariable
from stiefel_ops import gradStep
from utils import next_batch

from tensorflow.examples.tutorials.mnist import input_data


def ottVAEMNIST(niters, batch_size, lr, myTTrank, trainX):
    
    ########## Parameters ##########

    r = [1, myTTrank, myTTrank, myTTrank, 1]

    x_dim = 784
    h_dim = 256
    z_dim = 100
    nx = [4, 7, 4, 7]
    nh = [4, 4, 4, 4]
    nz = [2, 5, 5, 2]

    X = tf.placeholder(tf.float32, shape=[None, x_dim])
    z = tf.placeholder(tf.float32, shape=[None, z_dim])

    def xavier_init(size):
        in_dim = size[0]
        xavier_stddev = 1. / tf.sqrt(in_dim / 2.)
        return tf.random_normal(shape=size, stddev=xavier_stddev)

    # =============================== Q(z|X) ======================================

    # Q_W1 = tf.Variable(xavier_init([x_dim, h_dim]))
    Q_W1 = aOTTtfVariable(shape=[nh,nx], r=r, name='Q_W1')
    Q_b1 = tf.get_variable('Q_b1', shape=[h_dim], initializer=tf.zeros_initializer())

    Q_W2_mu = tf.Variable(xavier_init([h_dim, z_dim]))
    # Q_W2_mu = aOTTtfVariable(shape=[nz,nh], r=r, name='Q_W2_mu')
    Q_b2_mu = tf.get_variable('Q_b2_mu', shape=[z_dim], initializer=tf.zeros_initializer())

    Q_c1 = tf.get_variable('Qc1', shape=[1], initializer=tf.ones_initializer())
    # Q_c21 = tf.get_variable('Qc21', shape=[1])


    def Q(X):
        # o1 = tf.matmul(X, Q_W1) + Q_b1
        o1 = Q_c1*tf.transpose(Q_W1.mult(tf.transpose(X))) + Q_b1
        h = tf.nn.relu(o1)
        z = tf.matmul(h, Q_W2_mu) + Q_b2_mu
        # z_mu = tf.transpose(Q_W2_mu.mult(tf.transpose(h))) + Q_b2_mu
        return z


    # =============================== P(X|z) ======================================

    P_W1 = tf.Variable(xavier_init([z_dim, h_dim]))
    # P_W1 = aOTTtfVariable(shape=[nh,nz], r=r, name='P_W1')
    P_b1 = tf.get_variable('P_b1', shape=[h_dim], initializer=tf.zeros_initializer())

    P_W2 = tf.Variable(xavier_init([h_dim, x_dim]))
    # P_W2 = aOTTtfVariable(shape=[nx,nh], r=r, name='P_W2')
    P_b2 = tf.get_variable('P_b2', shape=[x_dim], initializer=tf.zeros_initializer())

    # P_c1 = tf.get_variable('Pc1', shape=[1])
    # P_c2 = tf.get_variable('Pc2', shape=[1])


    def P(z):
        o = tf.matmul(z, P_W1) + P_b1
        # o = tf.transpose(P_W1.mult(tf.transpose(z))) + P_b1
        h = tf.nn.relu(o)
        # logits = tf.transpose(P_W2.mult(tf.transpose(h))) + P_b2
        logits = tf.matmul(h, P_W2) + P_b2
        prob = tf.nn.sigmoid(logits)
        return prob, logits


    # =============================== TRAINING ====================================

    z = Q(X)
    _, logits = P(z)

    loss = tf.reduce_mean(tf.reduce_sum(tf.nn.sigmoid_cross_entropy_with_logits(logits=logits, labels=X), 1))
    
    ########## Optimizer and Gradient Updates ##########

    opt = tf.train.GradientDescentOptimizer(learning_rate=lr)
    # opt = tf.train.GradientDescentOptimizer(learning_rate=lr).minimize(loss)

    # EucGnVs = opt.compute_gradients(loss, [Q_b1, Q_b2_mu, Q_b2_sigma, P_b1, P_b2, P_W1, P_W2, Q_W2_mu, Q_W2_sigma, Q_W1])
    EucGnVs = opt.compute_gradients(loss, [Q_b1, Q_b2_mu, P_b1, P_b2, P_W1, P_W2, Q_W2_mu, Q_c1])
    myEucgrads = [(g, v) for g, v in EucGnVs]
    Eucupdate = opt.apply_gradients(myEucgrads)

    AottGnVs = opt.compute_gradients(loss, Q_W1.getQ())# + Q_W2_mu.getQ() + Q_W2_sigma.getQ() + P_W1.getQ() + P_W2.getQ())
    Steifupdate = [v.assign(gradStep(X=v, G=g)) for g, v in AottGnVs]

    sess = tf.Session()
    sess.run(tf.global_variables_initializer())

    nparams = np.sum([np.prod(v.get_shape().as_list()) for v in tf.trainable_variables()])
    print('Total number of parameters: ', nparams)

    t0 = time.time()
    losses = []
    tf.add_check_numerics_ops()

    for it in range(niters):
        X_mb = next_batch(x=trainX, batch_size=batch_size)
        # print(sess.run(AottGnVs[1][0], feed_dict={X: X_mb}))
        itloss = sess.run(loss, feed_dict={X: X_mb})
        _, _ = sess.run([Steifupdate, loss], feed_dict={X: X_mb})
        _, _ = sess.run([Eucupdate, loss], feed_dict={X: X_mb})
        
        # _, itloss = sess.run([opt, loss], feed_dict={X: X_mb})
        losses.append(itloss)
        
        print('Iter',it,'Loss',itloss)#, zmu, zlv)

    t1 = time.time()
    print('Took seconds:', t1 - t0)

    return t1, losses#, sess.run(Q_W1.getQ() + Q_W2_mu.getQ() + Q_W2_sigma.getQ() + P_W1.getQ() + P_W2.getQ())


if __name__ == "__main__":

    niters = 100
    batch_size = 64
    lr = 1e-6
    myTTranks = [5,5,5,5,5]#[1,5,10,20,50]
    tf.set_random_seed(0)

    ########## Dataset ##########
    mnist = input_data.read_data_sets('../../MNIST_data', one_hot=True)
    trainX = mnist.train.images

    losses = []
    for myTTrank in myTTranks:
        tf.reset_default_graph()
        mytime, loss = ottVAEMNIST(niters, batch_size, lr, myTTrank, trainX)
        losses.append(loss)

    # ## plot data
    # fig = plt.figure()
    # fig.show()
    # ax = fig.add_subplot(111)
    # ax.plot(np.arange(1,niters+1,1), losses[0], 'k-', label='rank=1')
    # ax.plot(np.arange(1,niters+1,1), losses[1], 'm-', label='rank=5')
    # ax.plot(np.arange(1,niters+1,1), losses[2], 'b-', label='rank=10')
    # ax.plot(np.arange(1,niters+1,1), losses[3], 'k:', label='rank=20')
    # ax.plot(np.arange(1,niters+1,1), losses[4], 'r-', label='rank=50')
    # plt.legend()
    # plt.show()