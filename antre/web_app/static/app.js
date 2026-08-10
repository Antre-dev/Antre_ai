const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const chat = document.getElementById("chat");


function addMessage(text, type) {
    const message = document.createElement("div");

    message.classList.add("message", type);

    if (type === "assistant") {
        message.innerHTML = marked.parse(text);
    } else {
        message.textContent = text;
    }

    chat.appendChild(message);

    chat.scrollTop = chat.scrollHeight;
}


form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = input.value.trim();

    if (!message) {
        return;
    }

    addMessage(message, "user");

    input.value = "";

    try {
        const response = await fetch("/chat", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        addMessage(data.response, "assistant");

    } catch (error) {
        console.error(error);

        addMessage(
            "error"
        );
    }
});