# main.py

from antre.agent import handle_message


def main():
    print("Antre up!.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            break

        try:
            response = handle_message(user_input)
            print(f"Antre: {response}\n")

        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()