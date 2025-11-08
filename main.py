import json
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

questions_set = json.load(open('Data/questions.json'))
mainDf = pd.read_excel('Data/data.xlsx')

game_state = {
    "df": mainDf.copy(),
    "traversal": None,
    "prev_club_checker": None
}


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


class inputData(BaseModel):
    SelectedAnswer: str


class outputData(BaseModel):
    question: str
    options: List[str]
    found: int


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


nodes = initializeNodes(questions_set)
linkNodes(nodes)


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("frontend/questions.html")


@app.get("/answers.html", response_class=HTMLResponse)
async def answers_page(name: str = ""):
    return FileResponse("frontend/answers.html")


@app.post("/reset")
def reset_game():
    global game_state
    game_state["df"] = mainDf.copy()
    game_state["traversal"] = nodes[0]
    game_state["prev_club_checker"] = None
    
    options = []
    for attr in game_state["traversal"].attribute:
        if attr in game_state["df"].columns:
            options += game_state["df"][attr].dropna().unique().tolist()
    options = sorted(list(set(options)))
    
    if options == ["no", "yes"]:
        options = ["Yes", "No"]
    
    return outputData(
        question=game_state["traversal"].question,
        options=options,
        found=0
    )

def node_traversal(df, temp, traversal, answer, prev_attribute, skip, prev_club_checker):
    if answer == "yes":
        if traversal.question.startswith("Is your character in") and str(traversal.questionId) != "q8":
            prev_club_checker = traversal.checker[0]
        for attribute in prev_attribute:
            filtered = df[df[attribute].astype(str).str.strip().str.lower().isin(traversal.checker)]
            temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
        df = temp
        traversal = traversal.yes or traversal.default
        
    elif answer == "no":
        for attribute in prev_attribute:
            filtered = df[~df[attribute].astype(str).str.strip().str.lower().isin(traversal.checker)]
            temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
        df = temp
        traversal = traversal.no or traversal.default
        
    else:
        if skip:
            traversal = getattr(getattr(traversal, "default", None), "default", None)
            skip = False
        else:
            traversal = getattr(traversal, "default", None)

        for attribute in prev_attribute:
            if attribute == "State" or attribute == "City":
                df = df[
                    (df[attribute].astype(str).str.strip().str.lower() == answer.lower().strip()) |
                    (df[attribute].astype(str).str.strip().str.lower() == "others") |
                    (df[attribute].astype(str).str.strip() == '')
                ]
                temp = df
            elif prev_attribute == ["DOMAIN", "DOMAIN2", "DOMAIN3"]:
                domain_columns = ["DOMAIN", "DOMAIN2", "DOMAIN3", "DOMAIN4"]
                for attribute in domain_columns:
                    if attribute in df.columns:
                        filtered = df[df[attribute].astype(str).str.strip().str.lower() == answer.strip().lower()]
                        temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
            else:
                df = df[df[attribute].astype(str).str.strip().str.lower() == answer.lower().strip()]
                temp = df
        df = temp
    return (df, traversal, answer, prev_attribute, skip, prev_club_checker)


def get_options(df, traversal, prev_club_checker):
    options = []
    print(f"Next Question: {traversal.question}")
    print(f"Next Attribute: {traversal.attribute}")

    if traversal.attribute == ["DOMAIN", "DOMAIN2", "DOMAIN3"]:
            print(f"Getting domains for club: {prev_club_checker}")
            
            club_domain_pairs = [
                ("CLUB", "DOMAIN"),
                ("CLUB2", "DOMAIN2"),
                ("CLUB3", "DOMAIN3"),
                ("CLUB4", "DOMAIN4")
            ]
            
            tempDomains = []
            
            if prev_club_checker:
                for idx, row in df.iterrows():
                    for club_col, domain_col in club_domain_pairs:
                        if club_col in df.columns and domain_col in df.columns:
                            club_val = str(row[club_col]).lower().strip()
                            domain_val = str(row[domain_col]).strip()
                            
                            if club_val == prev_club_checker and domain_val and domain_val != 'nan':
                                if domain_val not in tempDomains:
                                    tempDomains.append(domain_val)
                                    print(f"Found: {club_col}={club_val} → {domain_col}={domain_val}")
                
                if tempDomains:
                    options = sorted(tempDomains)
                    print(f"Final domains for '{prev_club_checker}': {options}")
                else:
                    print(f" No domains found for '{prev_club_checker}'")
                    options = ["No domains found"]
            else:
                print("No club selected, getting all domains")
                domain_columns = ["DOMAIN", "DOMAIN2", "DOMAIN3", "DOMAIN4"]
                for attr in domain_columns:
                    if attr in df.columns:
                        values = df[attr].dropna().unique().tolist()
                        options += [str(x).strip() for x in values if str(x) != 'nan']
                options = sorted(list(set(options)))
        
    elif traversal.attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"]:
        options = ["Yes", "No"]
    elif traversal.attribute == ["slc/sdc/cr"]:
        options = ["Yes", "No"]
    else:
        for attr in traversal.attribute:
            if attr in df.columns:
                values = df[attr].dropna().unique().tolist()
                options += [str(x).strip() for x in values if str(x) != 'nan']
        options = sorted(list(set(options)))
    
    if options == ["no", "yes"]:
        options = ["Yes", "No"]

    return options

@app.post("/process", response_model=outputData)
def start(data: inputData):
    global game_state
    
    if game_state["traversal"] is None:
        game_state["traversal"] = nodes[0]
    
    traversal = game_state["traversal"]
    df = game_state["df"]
    prev_club_checker = game_state["prev_club_checker"]
    
    try:
        answer = data.SelectedAnswer.strip().lower()
        print(f"\n{'='*50}")
        print(f"Question: {traversal.question}")
        print(f"Answer: {answer}")
        print(f"Traversal attribute: {traversal.attribute}")
        print(f"Current prev_club_checker: {prev_club_checker}")
        print(f"Records before filtering: {len(df)}")
        
        prev_attribute = traversal.attribute
        skip = False
        
        if traversal.question == "What is your character's Branch?" and answer == "ece":
            skip = True
        
        
        temp = pd.DataFrame()
        out_question = ''

        if prev_attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"] and answer not in ["yes", "no"]:
            prev_club_checker = answer.lower().strip()
            print(f"Setting prev_club_checker to: {prev_club_checker}")
        if traversal!=None:
            (df, traversal, answer, prev_attribute, skip, prev_club_checker) = node_traversal(df, temp, traversal, answer, prev_attribute, skip,prev_club_checker)
            out_question = traversal.question
        game_state["df"] = df
        game_state["traversal"] = traversal
        game_state["prev_club_checker"] = prev_club_checker
        
        print(f"Records after filtering: {len(df)}")
        print(df)

        if len(df) == 1:
            found_name = df.iloc[0]["Name"]
            print(f"FOUND: {found_name}")
            return outputData(
                question="Found!",
                options=[found_name],
                found=1
            )
        elif len(df) == 0:
            print("NOT FOUND")
            return outputData(question="Can't find!!", options=["Can't find!!"], found=-1)
        
        if traversal is None and len(df) == 0:
            return outputData(question="End of questions", options=["Done"], found=0)
        if traversal is None and len(df) != 0:
            if len(df) > 1: 
                for trait in df["Trait1"].head(): 
                    out_question = trait
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
        if traversal:
            options = get_options(df, traversal, prev_club_checker)
        else:
            options = ["Yes", "No"]
        print(f"Options: {options}")
        
        while(len(options) == 1):
            print(f"AUTO-SKIPPING: Only one option '{options[0]}' available")
            auto_answer = options[0].strip().lower()
            prev_attribute = traversal.attribute
            skip = False
            
            if traversal.question == "What is your character's Branch?" and auto_answer == "ece":
                skip = True
            
            temp = pd.DataFrame()
            
            if prev_attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"] and auto_answer not in ["yes", "no"]:
                prev_club_checker = auto_answer.lower().strip()
                print(f"Setting prev_club_checker to: {prev_club_checker}")
            
            (df, traversal, auto_answer, prev_attribute, skip, prev_club_checker) = node_traversal(
                df, temp, traversal, auto_answer, prev_attribute, skip, prev_club_checker
            )
            
            game_state["df"] = df
            game_state["traversal"] = traversal
            game_state["prev_club_checker"] = prev_club_checker
            
            print(f"Records after auto-skip filtering: {len(df)}")
            
            if len(df) == 1:
                found_name = df.iloc[0]["Name"]
                print(f"FOUND after auto-skip: {found_name}")
                return outputData(
                    question="Found!",
                    options=[found_name],
                    found=1
                )
            elif len(df) == 0:
                print("NOT FOUND after auto-skip")
                return outputData(question="Can't find!!", options=["Can't find!!"], found=-1)
            
            if traversal is None:
                return outputData(question="End of questions", options=["Done"], found=0)
            
            options = get_options(df, traversal, prev_club_checker)
            print(f"Options after auto-skip: {options}")
            out_question = traversal.question
        return outputData(
            question=out_question,
            options=options,
            found=0
        )
        
    except Exception as e:
        import traceback
        print("ERROR in /process:", e)
        traceback.print_exc()
        return outputData(
            question="Backend error",
            options=[],
            found=-1
        )
    
    


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)