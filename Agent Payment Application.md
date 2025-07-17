现有的转账支付体系为人类用户开设，非常破碎割裂，不能互联互通，需要用户本人手动操作，亲自验证。我们的项目旨在通过crypto稳定币搭建统一通用的AI agent支付网络，支持不同的Agent之间直接转账支付。Crypto作为全球唯一的统一支付体系，支持网络内任意两点点对点直接转账支付，并且完全支持trading bot等机器人自动运行操作，因此可以为AI agent之间进行转账支付提供最高效、通用和可靠的途径。

通过我们的agent支付协议，payment agent可以通过稳定币在crypto网络里直接相互转账。整个过程可以分为三个部分。第一个部分是发款方的agent。Agent接受转账支付的发送方的支付方式，接收发送方的资金后转换成稳定币。例如发送方通过微信/支付宝转账，agent接收转账后，将资金转换成稳定币。第二步是稳定币进入crypto支付网络，发款方的agent与收款方的agent通过我们的协议，进行点对点直接转账。我们的协议提供Agent查找匹配、身份认证、安全验证、上下文共享等相应的支持。最后一个部分是收款方的agent接收汇入的稳定币，将稳定币通过成为收款方接受的收款方式转给收款方。例如收款方接受visa mastercard银行卡，那么收款方的agent就将稳定币转换汇入收款方的visa mastercard银行卡账户里。

![image](https://github.com/user-attachments/assets/d34d38af-5743-48fd-a5ab-067dea19d98d)

与目前的Agent支付方式比较，现有的各种支付渠道也相继推出自己的[agent](https://mp.weixin.qq.com/s/0Toc3e9bxk2PxOacuH1gPg)，支持agent通过他们完成支付。但是他们之间缺乏互联互通，例如用户通过支付宝的agent无法直接转账给Visa、万事达或者Stripe、PayPal的agent。他们之间依然需要一个统一通用的支付网络来进行衔接。这就像银行之间也可以直接进行相互转账，但由于银行太多，每个银行之间搭建支付渠道的成本太高，因此需要一个统一的支付网络（SWIFT）进行链接中转的桥梁，每个银行就只需支持和接入这个支付网络，无需跟其他银行对接。

相比于其他agent互联互通协议提出的[支付方案](https://mp.weixin.qq.com/s/wFVUDs31e6CKLpu8F3LDWg)，我们的优势在于crypto已经是一个非常成熟完善通用，安全可靠，得到充分验证、高度认可的支付网络。新提出的支付方案在技术上并未得到充分验证，效果未知，从头开发的成本也很高。并且还需要大力推广普及，让市场接受，成本高昂。并且这些方案主要还是中心化的，在效率、成本、通用性、安全性等方面不如crypto的去中心化网络。

payment agent结合application agent，可以让payment agent付款或收到钱后调用相应的application agent，触发相应的行为动作，实现广泛的应用场景。例如：

1. 一是可以应用于crypto trading，让多个agent分工协作，获取市场行情和用户交易需求、制定和执行交易策略。

2. 另一个是agent可以帮用户买东西，例如可以帮用户直接向航空公司的agent订机票，向酒店的agent订房，绕开携程、飞猪、美团等第三方平台，提高效率、节省以往第三方平台收取的佣金。

3. agent也可以帮助用户购买网上的付费数字内容，例如直接向歌手的agent购买歌曲，向知识博主购买课程音频或视频，无需经过qq音乐、得到这些第三方平台，这样用户可以以更低的价格购买，内容创作者也可以获得更多的收益。

![image](https://github.com/user-attachments/assets/854a36b7-2a93-4fe8-85a7-7893fadf948a)


**分工：**

1.**Agent interoperability protocol：** 基于A2A连接不同的agents，实现基本的通信；基于camel/langchain等多agent框架搭建multi agent network；通过Web3解决实现agents之间的支付，并且解决身份、验证、上下文共享等问题。

2. **Third-party payment agents：**：支持第三方支付方式（微信支付宝，visa mastercard等）出入金，并且转化为稳定币，通过我们的interoperability protocol在crypto网络相互转账。可以通过连接现有的支付[agents](https://mp.weixin.qq.com/s/0Toc3e9bxk2PxOacuH1gPg)或者通过调用第三方支付API来搭建新的支付agent。具体支持哪种类型的支付方式取决于能够接入或搭建什么支付方式的agent。

3. **Third-party application agents：**：与payment agent连接，实现支付应用场景，例如上面提到的crypto trading，买东西订票，知识内容付费。具体实现哪种类型的应用取决于能够接入或搭建什么应用的agent。


**开发计划：**

1. 这周开发实现Agent interoperability protocol，Third-party payment agents，Third-party application agents

2. 下周三者连调，互联互通
