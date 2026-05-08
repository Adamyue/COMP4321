# TA3 Ranker Math Explanation

## English (Demo-ready answer)

Our ranker is a TF-IDF cosine-similarity model with separate body and title indexes.

First, we preprocess the query by lowercasing, removing stop words, and Porter stemming.  
For example, `running` and `run` map to the same stem.  
If the user includes quoted phrases, we do an exact phrase check using positional postings in both body and title indexes, and only keep documents that satisfy all phrase constraints.

For scoring, we use normalized TF-IDF weights:

- Query term weight:

$$
w_q(t)=\frac{\mathrm{tf}_q(t)}{\max_{t'}\mathrm{tf}_q(t')}\cdot \mathrm{idf}(t)
$$

- Body term weight in document $d$:

$$
w_b(t,d)=\frac{\mathrm{tf}_b(t,d)}{\max_{t'}\mathrm{tf}_b(t',d)}\cdot \mathrm{idf}(t)
$$

- Title term weight in document $d$:

$$
w_{title}(t,d)=\alpha\cdot \frac{\mathrm{tf}_{title}(t,d)}{\max_{t'}\mathrm{tf}_{title}(t',d)}\cdot \mathrm{idf}(t)
$$

Then we merge body and title into one document vector:

$$
w_d(t)=w_b(t,d)+w_{title}(t,d)
$$

Our IDF is:

$$
\mathrm{idf}(t)=\log_2\left(\frac{N}{df(t)}\right)
$$

where $N$ is total indexed pages (with valid titles), and $df(t)$ is the number of documents containing term $t$.

Finally, we compute cosine similarity:

$$
\mathrm{score}(q,d)=\frac{\vec w_q\cdot \vec w_d}{\|\vec w_q\|\ \|\vec w_d\|}
$$

sort by descending score, and return top 50 results.

For title boost, in this project we set $\alpha=2.0$ when boost is enabled, and $\alpha=1.0$ when disabled (no extra title emphasis).  
So with boost on, title matches contribute about 2x relative weight compared with the same normalized TF-IDF signal in title without boost.

---

## 中文翻译

我们的排序器是一个基于 TF-IDF 的余弦相似度模型，并且标题和正文有独立倒排索引。

首先，我们对查询做预处理：转小写、去停用词、Porter 词干化。  
例如 `running` 和 `run` 会归并到同一个词干。  
如果用户输入了双引号短语，我们会用位置倒排在正文和标题里做精确短语匹配，只保留满足全部短语约束的文档。

打分时使用归一化 TF-IDF 权重：

- 查询项权重：

$$
w_q(t)=\frac{\mathrm{tf}_q(t)}{\max_{t'}\mathrm{tf}_q(t')}\cdot \mathrm{idf}(t)
$$

- 文档 $d$ 中正文项权重：

$$
w_b(t,d)=\frac{\mathrm{tf}_b(t,d)}{\max_{t'}\mathrm{tf}_b(t',d)}\cdot \mathrm{idf}(t)
$$

- 文档 $d$ 中标题项权重：

$$
w_{title}(t,d)=\alpha\cdot \frac{\mathrm{tf}_{title}(t,d)}{\max_{t'}\mathrm{tf}_{title}(t',d)}\cdot \mathrm{idf}(t)
$$

然后把正文和标题合并成一个文档向量：

$$
w_d(t)=w_b(t,d)+w_{title}(t,d)
$$

我们的 IDF 定义是：

$$
\mathrm{idf}(t)=\log_2\left(\frac{N}{df(t)}\right)
$$

其中 $N$ 是已索引页面总数（有有效标题的页面），$df(t)$ 是包含该词项的文档数。

最后计算余弦相似度：

$$
\mathrm{score}(q,d)=\frac{\vec w_q\cdot \vec w_d}{\|\vec w_q\|\ \|\vec w_d\|}
$$

按分数降序排序，返回 top 50。

关于标题增强（title boost），本项目中开启时设 $\alpha=2.0$，关闭时 $\alpha=1.0$（即不额外增强标题）。  
所以开启后，标题匹配在相同归一化 TF-IDF 条件下大约有 2 倍贡献。

---

## No-Formula Oral Version (English)

Our ranking pipeline is straightforward.

First, we preprocess the query: lowercase, remove stop words, and stem words. If the query contains quoted text, we treat it as an exact phrase and only keep documents where that phrase appears in order.

Then we score documents using TF-IDF in a vector-space model. In words, each term weight is term-frequency times inverse-document-frequency, divided by the maximum term frequency for normalization. We do this for the query and for each document.

For the document side, we compute body weights and title weights separately, then add them together into one document vector.

For each candidate document, we compute cosine similarity against the query vector and rank by score in descending order.

We also apply title boost: title matches are given extra importance compared to body matches. In our implementation, boost-on uses alpha = 2.0, and boost-off uses alpha = 1.0. This helps pages with strong title matches move up in ranking.

Finally, we return the top 50 results and display score, title, URL, metadata, keywords, parent links, and child links in the UI.

## 无公式口语版（中文）

我们的排序流程是：先预处理查询，再做加权打分，最后按相似度排序。

第一步，查询预处理：转小写、去停用词、词干化。双引号部分按精确短语处理，只有标题或正文里按顺序出现该短语的页面才会保留。

第二步，打分采用 TF-IDF。口头上可以说：每个词的权重是“词频乘以逆文档频率，再除以该文本中的最大词频做归一化”。查询向量和文档向量都按这个方式构建。

第三步，文档向量由两部分组成：正文权重和标题权重。两者先分别计算，再合并成同一个文档向量。

第四步，计算查询向量和文档向量的 cosine similarity（余弦相似度），按分数从高到低排序，返回 top 50。

最后是 title boost：我们把标题部分乘上 alpha。当前实现中，开启 boost 时 alpha = 2.0，关闭时 alpha = 1.0，所以开启后标题命中的贡献更大，排名会更靠前。