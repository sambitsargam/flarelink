# **Flarelink: AI-Powered Blockchain Agent**  

Flarelink is a **WhatsApp and SMS-based AI agent** built on the **Flare blockchain**, enabling seamless blockchain interactions. Users can perform **on-chain** operations (e.g., swaps, sending transactions) and access **verifiable Web3 knowledge** using **TEE-secured LLMs** (Trusted Execution Environment-secured Large Language Models).  

## **Key Features**  
- **AI-Powered Queries**: Ask any question related to the **Flare blockchain** and get real-time, **verifiable** responses.  
- **On-Chain Actions**: Execute blockchain operations like **swaps**, **send transactions**, and more via **WhatsApp/SMS**.  
- **TEE Security**: Use **Trusted Execution Environments** to secure sensitive operations and ensure data privacy.  
- **RAG Context Injection**: Enhance AI responses with **real-time blockchain data** (from sources like **BigQuery**).  
- **Intelligent Context Management**: Optimize responses using **dynamic relevance scoring**, **context window optimization**, and **source verification**.  
- **Multimodal Interaction**: Engage with the blockchain via **text, voice**, and **messaging apps**.  


## **System Architecture**  

1. **Input Layer**: Accepts user queries from **WhatsApp**, **SMS**, or APIs.  
2. **Processing Layer**:  
   - Converts **imperative commands** (e.g., "Send 100 FLR to 0x00..") into **declarative blockchain instructions**.  
   - Routes **queries** to a **TEE-secured LLM** for execution and privacy.  
3. **Knowledge Pipeline**:  
   - **Ingests** Web3 data from **Flare blockchain**, **BigQuery**, and **open-source** repositories.  
   - Stores data in a **vector database** for efficient retrieval.  
4. **AI Layer**:  
   - Implements **RAG (Retrieval-Augmented Generation)** for domain-specific outputs.  
   - Uses **dynamic context management** to ensure the **most relevant** and **verified** responses.  
5. **Output Layer**: Delivers **human-readable** results or executes **blockchain transactions**.  


## **Getting Started**  

### **Prerequisites**  
Ensure you have the following installed:

- Python (≥ 3.10)  
- Docker (for TEE simulation)  
- Twilio account (for SMS/WhatsApp integration)  
- Access to Flare blockchain RPC and BigQuery APIs
- Gemini API Key



## **Usage**  

### **Interact via WhatsApp/SMS**  
1. Send a message to your **Twilio WhatsApp** number:  
   - Example:  
   ```text
   Swap 100 FLR for USDC
   ```
2. Receive a confirmation and on-chain transaction hash.

### **Common Queries**  
- **On-chain Operations**:  
    - "Send 50 FLR to 0x1234..."  
    - "Check my wallet balance."  
- **Blockchain Knowledge**:  
    - "What is Flare Time Series Oracle (FTSO)?"  
    - "Explain how FAssets work."  



## **Future Improvements**  
- Expand support for **voice** commands.  
- Implement **multi-chain** interactions.  
- Add **user authentication** via wallet signatures.  


## **Contributing**  
Contributions are welcome! Feel free to open issues and submit pull requests.

1. Fork the repository.  
2. Create a new branch:  
   ```bash
   git checkout -b feature/new-feature
   ```
3. Commit changes:  
   ```bash
   git commit -m "Add new feature"
   ```
4. Push and open a pull request.  


## **License**  
MIT License. See `LICENSE` for more information.


## **Contact**  
For questions and collaboration, reach out via:  
- **X**: [@sambitsargam](https://x.com/sambitsargam)  
