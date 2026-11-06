from src.rag import answer_query

def main():
    print("--- Academic RAG Prototype (CLI) ---")
    course_filter = input("Filter by course ID (leave blank for all): ").strip() or None
    print(f"Active Course Filter: {course_filter or 'None'}")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            q = input("\nStudent: ").strip()
            if not q or q.lower() in ("exit", "quit"):
                break

            result = answer_query(q, course_id=course_filter)
            print(f"\nAssistant:\n{result['answer']}\n")
            print("--- Retrievable Citations ---")
            for s in result["sources"]:
                print(f"- {s['filename']} (Page {s['page_number']}) | Similarity: {s['score']}")

        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()