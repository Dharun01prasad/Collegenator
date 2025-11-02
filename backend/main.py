import json, pandas as pd

class Node:
    def __init__(self, questionId, question, attribute, options, yes, no, default, checker):
        self.questionId = questionId
        self.question = question
        self.attribute = attribute
        self.options = options
        self.yes = yes
        self.no = no
        self.default = default
        self.checker = checker


def initializeNodes(questions_set):
    nodes = []
    for i in range(len(questions_set)):
        qid = f"q{i+1}"
        qdata = questions_set[qid]

        nodes.append(Node(
            questionId=qid,
            question=qdata["question"],
            attribute=qdata["attribute"],
            options=qdata["options"],
            yes=qdata["next_question"]["yes"],
            no=qdata["next_question"]["no"],
            default=qdata["next_question"]["default"],
            checker=qdata["checker"]
        ))
    return nodes


def linkNodes(nodes):
    id_map = {node.questionId: node for node in nodes}

    for node in nodes:
        node.yes = id_map.get(node.yes) if node.yes not in ["None", None] else None
        node.no = id_map.get(node.no) if node.no not in ["None", None] else None
        node.default = id_map.get(node.default) if node.default not in ["None", None] else None


def start(nodes, df):
    traversal = nodes[0]

    while traversal:
        if len(df) == 1:
            print("Found!")
            break
        elif len(df) == 0:
            print("Can't Find")
            break 
        answer = input(f"{traversal.question} : ").strip().lower()

        temp = pd.DataFrame()
        prev_attribute = traversal.attribute
        if answer == "yes":
            for attribute in prev_attribute:
                filtered = df[df[attribute].astype(str).str.strip().str.lower().isin(traversal.checker)]
                temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
            df = temp
            traversal = traversal.yes or traversal.default
        elif answer == "no":
            for attribute in prev_attribute:
                print("Attribute: ", attribute, df[attribute])
                filtered = df[~df[attribute].astype(str).str.strip().str.lower().isin(traversal.checker)]
                temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
                df = temp
            traversal = traversal.no or traversal.default
        else:
            traversal = traversal.default
            for attribute in prev_attribute:
                if(attribute == "State"):
                    print("Special State Handling")
                    df = df[(df[attribute].astype(str).str.strip().str.lower() == answer.strip().lower()) |
    (df[attribute].isna()) |
    (df[attribute].astype(str).str.strip() == '')]
                else:
                    print(df[attribute], type(df[attribute]))
                    df = df[df[attribute].astype(str).str.strip().str.lower() == answer.strip().lower()]

        print("After: ", df)
        print(f"Remaining options: {len(df)}")
        if traversal is None:
            break
    if len(df) > 1:
        for trait in df["Trait1"].head():
            answer = input(f"{trait}: ").strip().lower()
            if answer == "yes":
                df = df[df["Trait1"].astype(str).str.strip().str.lower() == trait.strip().lower()]
            elif answer == "no":
                df = df[~(df["Trait1"].astype(str).str.strip().str.lower() == trait.strip().lower())]
            if len(df) == 1:
                df.head()
                print("Found!")
                break
            elif len(df) == 0:
                print("Can't Find")
                break
            print(f"Remaining options: {len(df)}")
        
        


if __name__ == "__main__":
    questions_set = json.load(open('Data/questions.json'))
    df = pd.read_excel('Data/data.xlsx')
    copy = df.copy()

    nodes = initializeNodes(questions_set)

    linkNodes(nodes)
    print(f"Initial options: {len(copy)}")
    start(nodes, copy)
