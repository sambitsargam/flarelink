import express from 'express';
import bodyParser from 'body-parser';
import twilio from "twilio";
import axios from "axios";
require("dotenv").config();
const app = express();
app.use(bodyParser.json()); // for parsing application/json



const twilioClient = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);


(async () => {

    const app = express();
    // Parse URL-encoded bodies (as sent by HTML forms)
    app.use(bodyParser.urlencoded({ extended: true }));

    // Parse JSON bodies (as sent by API clients)
    app.use(bodyParser.json());

    app.post("/api/send-whatsapp", async (req, res) => {
        console.log("Headers:", req.headers);
        console.log("Body:", req.body);
        const from = req.body.From;
        let body = req.body.Body;


        console.log("Received WhatsApp message from", from, "with body:", body);

        try {
            // post the message to the AI model 'http://localhost:8080/api/routes/chat/'
            const response = await axios.post('http://localhost:8080/api/routes/chat/', {
                message: body,
                user: from
            });

            console.log("AI response:", response.data);

            const message = await twilioClient.messages.create({
                to: `${from}`,
                from: `whatsapp:${process.env.TWILIO_WHATSAPP_NUMBER}`,
                body: response.data.response
            });
            res.json({ success: true, message: "WhatsApp message sent with AI response.", sid: message.sid });
        } catch (error) {
            console.error("Failed to send WhatsApp message with AI response:", error);
            res.status(500).json({ success: false, message: "Failed to send WhatsApp message." });
        }
    });

    const PORT = process.env.PORT || 3001;
    app.listen(PORT, () => {
        console.log(`Server is running on port ${PORT}`);
    });
})();
