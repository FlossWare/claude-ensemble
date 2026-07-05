# CPU-Based LLM Training - Research & Resources

## 📚 Essential Papers (Must Read)

### 1. **Mamba: Linear-Time Sequence Modeling** ⭐⭐⭐
**Authors:** Albert Gu, Tri Dao (Princeton, CMU)  
**Published:** December 2023  
**Link:** https://arxiv.org/abs/2312.00752  
**GitHub:** https://github.com/state-spaces/mamba  

**Why Critical:**
- Replaces quadratic attention with linear SSM
- Matches transformer quality at 5× speed
- **CPU trainable!**

**Key Quote:**
> "Mamba enjoys fast inference (5× higher throughput than Transformers) and linear scaling in sequence length"

**Implementation Available:** Yes (Apache 2.0 license)

---

### 2. **BitNet: The Era of 1-bit LLMs** ⭐⭐⭐
**Authors:** Microsoft Research  
**Published:** February 2024  
**Link:** https://arxiv.org/abs/2402.17764  
**Follow-up:** BitNet b1.58 (October 2024)

**Why Critical:**
- 1.58-bit weights (not 16-bit)
- 10× memory reduction
- Same quality as FP16 models

**Key Results:**
- BitNet-3B matches Llama-3B at 1/10 the memory
- Training time comparable to FP16
- **Inference 10× faster on CPU**

**Code:** https://github.com/microsoft/BitNet

---

### 3. **RWKV: Reinventing RNNs for the Transformer Era** ⭐⭐
**Authors:** Bo Peng et al.  
**Published:** May 2023  
**Link:** https://arxiv.org/abs/2305.13048  
**GitHub:** https://github.com/BlinkDL/RWKV-LM

**Why Relevant:**
- RNN architecture (sequential, not parallel)
- O(n) complexity like Mamba
- Proven to scale to 14B parameters

**Community:** Very active, multiple implementations

---

### 4. **Chinchilla: Optimal Models Are Optimal Datasets** ⭐⭐⭐
**Authors:** DeepMind (Hoffmann et al.)  
**Published:** March 2022  
**Link:** https://arxiv.org/abs/2203.15556

**Why Critical:**
- **Scaling laws:** 10× more data > 10× more parameters
- Chinchilla-70B beats GPT-3-175B with better data
- Implication: **Quality data > model size**

**Our Takeaway:**
- Don't need massive models
- Focus on curated, specialized datasets
- 1B params + great data > 10B params + random data

---

### 5. **Knowledge Distillation (Hinton et al., 2015)** ⭐⭐
**Authors:** Geoffrey Hinton, Oriol Vinyals, Jeff Dean  
**Published:** March 2015  
**Link:** https://arxiv.org/abs/1503.02531

**Why Foundational:**
- Teacher-student learning
- Small model learns from large model
- Proven to preserve 90-95% of quality

**Modern Applications:**
- DeepSeek-R1: 671B → 70B distillation
- DistilBERT: BERT → 40% size, 95% quality
- MiniLM: 66M params, matches BERT-base

---

### 6. **Mixture of Depths (Meta, 2024)** ⭐
**Authors:** David Raposo et al. (Meta AI)  
**Published:** April 2024  
**Link:** https://arxiv.org/abs/2404.02258

**Why Interesting:**
- Not all tokens need all layers
- 50% FLOPs reduction
- Same quality

**Application:**
- Dynamic layer skipping
- CPU benefits from less computation

---

## 🎤 Talks & Conferences

### Must-Watch Talks

#### 1. **"Mamba Explained" - Yannic Kilcher**
**Platform:** YouTube  
**Link:** https://www.youtube.com/watch?v=N6Piou4oYx8  
**Duration:** 45 min  
**Level:** Technical deep dive

**Summary:**
- Best explanation of Mamba architecture
- Compares to transformers
- Shows why it's faster

---

#### 2. **"The Era of 1-bit LLMs" - Microsoft Research**
**Platform:** YouTube  
**Link:** https://www.youtube.com/watch?v=HlJZEKTTdQQ  
**Duration:** 30 min  
**Level:** Accessible

**Summary:**
- BitNet overview
- Live demos on CPU
- Quantization techniques

---

#### 3. **"Training LLMs on Your Laptop" - Andrej Karpathy**
**Platform:** YouTube  
**Link:** https://www.youtube.com/watch?v=kCc8FmEb1nY  
**Duration:** 2 hours  
**Level:** Tutorial

**Summary:**
- nanoGPT walkthrough
- Training from scratch
- CPU optimization tips

**Code:** https://github.com/karpathy/nanoGPT

---

#### 4. **NeurIPS 2023: Efficient Transformers Workshop**
**Platform:** NeurIPS (recordings available)  
**Topics:**
- State Space Models (Mamba)
- Sparse attention
- Quantization methods

**Proceedings:** https://neurips.cc/virtual/2023/workshop/66537

---

#### 5. **"RWKV - RNNs Strike Back" - EleutherAI**
**Platform:** YouTube  
**Link:** https://www.youtube.com/watch?v=x8pW19wKfXQ  
**Duration:** 1 hour

**Summary:**
- Why RNNs for modern LLMs
- RWKV architecture
- Training tips

---

## 🏛️ Research Groups to Follow

### 1. **Tri Dao's Lab (Princeton)**
- Mamba author
- FlashAttention creator
- Focus: Efficient architectures
- Twitter: @tri_dao
- Papers: https://tridao.me/publications/

### 2. **EleutherAI**
- Open-source LLM research
- RWKV, Pythia models
- Discord: Very active community
- Website: https://www.eleuther.ai/

### 3. **Microsoft Research**
- BitNet team
- Quantization research
- DeepSpeed (distributed training)
- GitHub: https://github.com/microsoft/DeepSpeed

### 4. **Hugging Face**
- Transformers library
- PEFT (Parameter-Efficient Fine-Tuning)
- Training tutorials
- Hub: https://huggingface.co/docs

---

## 📖 Textbooks & Courses

### Books

#### 1. **"Deep Learning" - Goodfellow, Bengio, Courville**
**Free Online:** https://www.deeplearningbook.org/  
**Relevant Chapters:**
- Chapter 10: Sequence Modeling (RNNs, LSTMs)
- Chapter 12: Applications (Language Modeling)

#### 2. **"Speech and Language Processing" - Jurafsky & Martin**
**Free Online:** https://web.stanford.edu/~jurafsky/slp3/  
**Relevant:**
- Chapter 7: Neural Networks
- Chapter 9: RNNs and LSTMs

---

### Online Courses

#### 1. **"Neural Networks: Zero to Hero" - Andrej Karpathy**
**Platform:** YouTube  
**Link:** https://www.youtube.com/playlist?list=PLAqhIrjkxbuWI23v9cThsA9GvCAUhRvKZ  
**Duration:** ~10 hours  
**Level:** Beginner to Advanced

**Modules:**
- Micrograd (autograd from scratch)
- Makemore (character-level LM)
- nanoGPT (GPT from scratch)

**Why Essential:**
- Builds intuition from first principles
- CPU-focused (no GPU required)
- Code-first approach

---

#### 2. **Stanford CS224N: NLP with Deep Learning**
**Platform:** YouTube  
**Link:** https://www.youtube.com/playlist?list=PLoROMvodv4rMFqRtEuo6SGjY4XbRIVRd4  
**Instructors:** Chris Manning, Shikhar Murty

**Relevant Lectures:**
- Lecture 11: Transformers
- Lecture 12: Pretraining
- Lecture 13: Model Analysis

---

#### 3. **Fast.ai: Practical Deep Learning**
**Platform:** https://course.fast.ai/  
**Focus:** Practitioners, not researchers  
**GPU:** Optional (works on CPU)

**Why Useful:**
- Transfer learning techniques
- Fine-tuning strategies
- Deployment best practices

---

## 🛠️ Implementation Resources

### GitHub Repositories

#### 1. **Mamba (Official)**
**Link:** https://github.com/state-spaces/mamba  
**Stars:** 15k+  
**License:** Apache 2.0

**What's Included:**
- Full Mamba implementation
- Pre-trained checkpoints
- Training scripts
- Benchmarks

**CPU Support:** Yes

---

#### 2. **BitNet (Microsoft)**
**Link:** https://github.com/microsoft/BitNet  
**Stars:** 8k+

**What's Included:**
- BitLinear layers
- Quantization utils
- Training recipes
- Inference optimizations

---

#### 3. **nanoGPT (Karpathy)**
**Link:** https://github.com/karpathy/nanoGPT  
**Stars:** 40k+

**Why Valuable:**
- Minimal, readable code (~300 lines)
- Trains on CPU (small models)
- Great for learning architecture

**Our Use:**
- Template for distributed training
- Tokenization pipeline
- Validation harness

---

#### 4. **RWKV-LM**
**Link:** https://github.com/BlinkDL/RWKV-LM  
**Stars:** 12k+

**What's Included:**
- Full RWKV implementation
- Models up to 14B params
- CPU inference code
- Training guides

---

#### 5. **DeepSpeed (Microsoft)**
**Link:** https://github.com/microsoft/DeepSpeed  
**Stars:** 35k+

**Features:**
- Distributed training
- ZeRO optimizer (memory efficient)
- CPU offloading
- 1-bit Adam

**CPU Training:** Explicitly supported

---

### Hugging Face Resources

#### Model Checkpoints
**Filter:** CPU-friendly models

1. **mamba-130m, mamba-370m, mamba-790m**
   - Pre-trained SSMs
   - Can fine-tune on CPU

2. **RWKV-14B**
   - RNN architecture
   - CPU inference ready

3. **DistilBERT, TinyBERT**
   - Distilled transformers
   - Fast CPU inference

**Search:** https://huggingface.co/models?pipeline_tag=text-generation&sort=downloads

---

## 📊 Datasets

### Code Datasets

#### 1. **The Stack (Hugging Face)**
**Link:** https://huggingface.co/datasets/bigcode/the-stack  
**Size:** 6TB of code  
**Languages:** 358 programming languages

**Subsets:**
- the-stack-dedup (3TB)
- the-stack-smol (250GB)

**Our Use:** Python, JavaScript, Shell subsets

---

#### 2. **CodeParrot**
**Link:** https://huggingface.co/datasets/codeparrot/github-code  
**Size:** 115GB  
**Focus:** Clean, high-quality code

---

### Text Datasets

#### 1. **RedPajama**
**Link:** https://huggingface.co/datasets/togethercomputer/RedPajama-Data-1T  
**Size:** 1.2 trillion tokens  
**Quality:** High (filtered)

**Subsets:**
- CommonCrawl (878B tokens)
- StackExchange (20B tokens)
- GitHub (59B tokens)

---

#### 2. **Pile (EleutherAI)**
**Link:** https://pile.eleuther.ai/  
**Size:** 825GB  
**Diversity:** 22 sources

**Includes:**
- Books
- ArXiv papers
- Code (GitHub)
- StackExchange

---

## 🔬 Active Research Areas (2024-2025)

### Hot Topics

1. **Hybrid Architectures**
   - Mamba + Attention (best of both)
   - Paper: "Jamba" (AI21 Labs, 2024)

2. **Quantization Beyond BitNet**
   - Sub-1-bit representations
   - Learned quantization

3. **CPU-Specific Optimizations**
   - AVX-512 kernels
   - Cache-aware algorithms

4. **Continual Learning**
   - Update models without full retraining
   - Elastic Weight Consolidation

5. **Mixture of Experts**
   - Sparse activation
   - Conditional computation

---

## 📢 Communities

### Discord Servers

1. **EleutherAI**
   - Very active
   - #research, #training channels
   - Link: https://discord.gg/eleutherai

2. **Hugging Face**
   - #transformers-training
   - #model-optimization

3. **LAION**
   - Open-source AI
   - Dataset discussions

---

### Reddit

1. **r/LocalLLaMA**
   - Focus: Running LLMs locally
   - CPU training discussions
   - Link: https://reddit.com/r/LocalLLaMA

2. **r/MachineLearning**
   - Research papers
   - Implementation discussions

---

### Twitter/X

**Key Accounts:**
- @tri_dao (Mamba author)
- @karpathy (Teaching, fundamentals)
- @GuggerSylvain (Hugging Face)
- @BlinkDL_AI (RWKV)
- @hardmaru (Google Brain)

---

## 🎯 Recommended Learning Path

### Month 1: Foundations
1. Watch Karpathy's "Neural Networks: Zero to Hero"
2. Read Mamba paper (skim math, focus on results)
3. Clone nanoGPT, train toy model on CPU

### Month 2: Architecture Deep Dive
1. Read BitNet paper
2. Study Mamba implementation
3. Compare: Transformer vs Mamba vs RWKV

### Month 3: Hands-On
1. Implement simple Mamba block
2. Train on small dataset (10k examples)
3. Benchmark vs PyTorch transformer

### Month 4: Distributed Training
1. Study DeepSpeed documentation
2. Set up 2-node distributed training
3. Scale to full 8-server cluster

---

## 📝 Next Actions

### This Week
- [ ] Read Mamba paper (focus on Section 3)
- [ ] Watch Karpathy's nanoGPT video
- [ ] Clone Mamba repo, run inference example

### This Month
- [ ] Complete Karpathy's course
- [ ] Read BitNet paper
- [ ] Join EleutherAI Discord

### This Quarter
- [ ] Implement toy Mamba from scratch
- [ ] Set up distributed training
- [ ] Train first 10M param model

---

## 💬 Questions to Explore

1. **Can we combine Mamba + BitNet?**
   - Linear complexity + 1.58-bit weights
   - Potentially 100× CPU speedup

2. **What's the smallest viable model?**
   - 10M? 100M? 1B?
   - Quality vs size tradeoff

3. **Specialized vs General?**
   - 4×250M experts or 1×1B generalist
   - Our data is domain-specific (code, k8s, docs)

4. **Training data quality?**
   - Curated 10GB > random 100GB?
   - How to measure quality?

---

**Ready to dive in?** Start with Karpathy's videos this week! 🚀
