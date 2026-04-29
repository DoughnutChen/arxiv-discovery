# arXiv Discovery：LLM

- 搜索关键词：`LLM`
- arXiv 分类：`cs.IR / cs.CL / cs.AR / cs.LG / cs.AI / cs.DC`
- 排序方式：`relevance/descending`
- 处理论文数：`5`
- 备注：`无`

## 整体摘要

本批论文集中探讨了大型语言模型（LLM）在不同应用场景下的性能优化、部署挑战和系统设计问题。研究问题覆盖了从提高LLM推理的确定性、优化分布式推理平台设计，到增强LLM的可靠性和减少内部不一致性。这些论文展示了LLM在技术发展和应用部署中的多样性和复杂性，提出了多种方法来解决LLM在实际应用中的挑战，包括系统级优化、硬件加速器设计和评估框架的构建。这些研究对于理解LLM的内部机制、提升其在特定任务上的表现以及指导未来硬件和软件协同设计具有重要的学术和应用价值。

## 1. RETA-LLM: A Retrieval-Augmented Large Language Model Toolkit

- arXiv ID：`2306.05212v1`
- 链接：[Abstract](https://arxiv.org/abs/2306.05212v1)，[PDF](https://arxiv.org/pdf/2306.05212v1.pdf)
- 作者：Jiongnan Liu；Jiajie Jin；Zihan Wang；Jiehan Cheng；Zhicheng Dou；Ji-Rong Wen
- 发布/更新：2023-06-08T14:10:54Z / 2023-06-08T14:10:54Z

### 研究问题
论文旨在解决LLM在生成用户请求响应时可能出现的虚构回答问题，通过将信息检索（IR）系统与LLM结合，即检索增强型LLM，来生成更符合事实的文本。

### 研究方法
研究者开发了RETA-LLM工具包，提供了一个完整的流程，包括请求重写、文档检索、段落提取、答案生成和事实检查模块，以支持IR系统和LLM之间的更好交互。

### 研究结论
① RETA-LLM通过请求重写模块改进用户请求的完整性和清晰度。
② 文档检索模块根据修订请求从外部语料库检索相关文档。
③ 段落提取模块从检索到的文档中提取与用户请求相关的片段。
具体领域
- 信息检索 / 大型语言模型

### 推荐原因
RETA-LLM工具包为构建定制化的领域特定LLM系统提供了一个模块化的方法，有助于研究者和实践者在LLM应用中更好地整合IR技术。

## 2. FBI-LLM: Scaling Up Fully Binarized LLMs from Scratch via Autoregressive Distillation

- arXiv ID：`2407.07093v1`
- 链接：[Abstract](https://arxiv.org/abs/2407.07093v1)，[PDF](https://arxiv.org/pdf/2407.07093v1.pdf)
- 作者：Liqun Ma；Mingjie Sun；Zhiqiang Shen
- 发布/更新：2024-07-09T17:59:48Z / 2024-07-09T17:59:48Z

### 研究问题
论文提出了一种全新的全二值化大型语言模型（FBI-LLM），探讨了如何从头开始训练全二值化LLM以匹配全精度模型的性能。

### 研究方法
研究者采用了自回归蒸馏（AD）损失函数，并保持与常规LLM预训练相当的模型尺寸和训练数据量，以实现在困惑度和特定任务效果方面的竞争力结果。

### 研究结论
① FBI-LLM能够在不同的模型尺寸（130M, 1.3B, 7B）上从头开始训练全二值化LLM。
② 自回归蒸馏是训练二值化LLM的关键。
③ 与全精度模型相比，FBI-LLM在困惑度和多个下游任务上展现出较小的性能差距。
具体领域
- 模型压缩 / 大型语言模型

### 推荐原因
FBI-LLM的研究为全二值化LLM的训练提供了新的方法，对于设计专用于全1位LLM的硬件具有启发性，有助于推动LLM在存储和效率方面的优化。

## 3. Systematic Evaluation of LLM-as-a-Judge in LLM Alignment Tasks: Explainable Metrics and Diverse Prompt