import json
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from pathlib import Path
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent

# Mount static files
app.mount("/frontend", StaticFiles(directory=str(BASE_DIR / "frontend")), name="frontend")

# Load data files with proper path handling
try:
    with open(BASE_DIR / 'Data' / 'questions.json', 'r') as f:
        questions_set = json.load(f)
    mainDf = pd.read_excel(BASE_DIR / 'Data' / 'data.xlsx')
except FileNotFoundError as e:
    print(f"ERROR: Could not find data files: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Files in directory: {os.listdir('.')}")
    # Create dummy data for testing
    questions_set = {}
    mainDf = pd.DataFrame()

# CHANGED: Use dictionary to store multiple user sessions instead of single global state
user_sessions = {}


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
    session_id: Optional[str] = None  # CHANGED: Added session_id


class outputData(BaseModel):
    question: str
    options: List[str]
    found: int
    session_id: Optional[str] = None  # CHANGED: Added session_id


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


nodes = initializeNodes(questions_set) if questions_set else []
if nodes:
    linkNodes(nodes)


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))

@app.get("/copyrights.html", response_class=HTMLResponse)
async def copyrights():
    return FileResponse(str(BASE_DIR / "frontend" / "copyrights.html"))

@app.get("/questions.html", response_class=HTMLResponse)
async def questions_page():
    return FileResponse(str(BASE_DIR / "frontend" / "questions.html"))


@app.get("/answers.html", response_class=HTMLResponse)
async def answers_page(name: str = ""):
    return FileResponse(str(BASE_DIR / "frontend" / "answers.html"))


@app.post("/reset")
def reset_game():
    # CHANGED: Create new session for each user
    session_id = str(uuid.uuid4())
    
    user_sessions[session_id] = {
        "df": mainDf.copy(),
        "traversal": nodes[0] if nodes else None,
        "prev_club_checker": None,
        "trait_check_mode": False,
        "current_trait_index": 0,
        "traits_to_check": []
    }
    
    if not nodes:
        return outputData(
            question="No data available",
            options=["Error: Data files not found"],
            found=-1,
            session_id=session_id
        )
    
    game_state = user_sessions[session_id]
    
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
        found=0,
        session_id=session_id  # CHANGED: Return session_id
    )

def node_traversal(df, temp, traversal, answer, prev_attribute, skip, prev_club_checker):
    answer = answer.strip().lower()
    if answer == "yes":
        if traversal.question.startswith("Is your character in") and str(traversal.questionId) != "q8":
            prev_club_checker = traversal.checker[0]
        for attribute in prev_attribute:
            filtered = df[df[attribute].astype(str).str.strip().str.lower().isin(traversal.checker)]
            temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
        df = temp
        traversal = traversal.yes or traversal.default
        
    elif answer == "no":
        if prev_attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"]:
            club_columns = ["CLUB", "CLUB2", "CLUB3", "CLUB4"]
            mask = pd.Series([True] * len(df), index=df.index)
            for club_col in club_columns:
                if club_col in df.columns:
                    mask &= ~df[club_col].astype(str).str.strip().str.lower().isin(traversal.checker)
            df = df[mask]
        else:
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
                            domain_val = str(row[domain_col]).strip().lower().title()
                            
                            if club_val == prev_club_checker and domain_val and domain_val != 'Nan':
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
        
    elif traversal.attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"] or traversal.attribute == ["CLUB-CHECKER"]:
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
    # CHANGED: Get session-specific game state
    if not data.session_id or data.session_id not in user_sessions:
        return outputData(
            question="Session expired. Please restart the game.",
            options=["Restart"],
            found=-1,
            session_id=None
        )
    
    game_state = user_sessions[data.session_id]
    
    if game_state["traversal"] is None and not game_state["trait_check_mode"]:
        game_state["traversal"] = nodes[0] if nodes else None
    
    if not nodes:
        return outputData(
            question="No data available",
            options=["Error: Data files not found"],
            found=-1,
            session_id=data.session_id
        )
    
    if game_state["trait_check_mode"]:
        df = game_state["df"]
        answer = data.SelectedAnswer.strip().lower()
        current_trait = game_state["traits_to_check"][game_state["current_trait_index"]]
        
        print(f"\n\nDEBUGGING Session {data.session_id}\n\nVALUES BEFORE: {df}")
        print(f"Trait check - Trait: {current_trait}, Answer: {answer}")
        
        if answer == "yes":
            df = df[df["Trait1"].astype(str).str.strip().str.lower() == current_trait.strip().lower()]
        elif answer == "no":
            df = df[~(df["Trait1"].astype(str).str.strip().str.lower() == current_trait.strip().lower())]
        
        game_state["df"] = df
        print(f"Remaining after trait filter: {len(df)}")
        print(f"\n\nVALUES AFTER: {df}\n\n\n")
        if len(df) == 1:
            found_name = df.iloc[0]["Name"]
            print(f"FOUND: {found_name}")
            game_state["trait_check_mode"] = False
            return outputData(
                question="Found!",
                options=[found_name],
                found=1,
                session_id=data.session_id
            )
        elif len(df) == 0:
            print("NOT FOUND")
            game_state["trait_check_mode"] = False
            return outputData(
                question="Can't find!!", 
                options=["Can't find!!"], 
                found=-1,
                session_id=data.session_id
            )
        
        game_state["current_trait_index"] += 1
        
        if game_state["current_trait_index"] < len(game_state["traits_to_check"]):
            next_trait = game_state["traits_to_check"][game_state["current_trait_index"]]
            print(f"Next trait: {next_trait}")
            return outputData(
                question=f"{next_trait}?",
                options=["Yes", "No"],
                found=0,
                session_id=data.session_id
            )
        else:
            game_state["trait_check_mode"] = False
            if len(df) == 1:
                found_name = df.iloc[0]["Name"]
                return outputData(
                    question="Found!", 
                    options=[found_name], 
                    found=1,
                    session_id=data.session_id
                )
            else:
                return outputData(
                    question="Can't find!!", 
                    options=["Can't find!!"], 
                    found=-1,
                    session_id=data.session_id
                )
    
    traversal = game_state["traversal"]
    df = game_state["df"]
    prev_club_checker = game_state["prev_club_checker"]
    
    try:
        answer = data.SelectedAnswer.strip().lower()
        print(f"\n{'='*50}")
        print(f"Session: {data.session_id}")
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
        
        if prev_attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"] and answer == "yes":
            prev_club_checker = traversal.checker[0].lower().strip()
            print(f"Setting prev_club_checker to: {prev_club_checker}")
        
        (df, traversal, answer, prev_attribute, skip, prev_club_checker) = node_traversal(
            df, temp, traversal, answer, prev_attribute, skip, prev_club_checker
        )

        game_state["df"] = df
        game_state["traversal"] = traversal
        game_state["prev_club_checker"] = prev_club_checker
        
        print(f"Records after filtering: {len(df)}")

        if len(df) == 1:
            found_name = df.iloc[0]["Name"]
            print(f"FOUND: {found_name}")
            return outputData(
                question="Found!",
                options=[found_name],
                found=1,
                session_id=data.session_id
            )
        elif len(df) == 0:
            print("NOT FOUND")
            return outputData(
                question="Can't find!!", 
                options=["Can't find!!"], 
                found=-1,
                session_id=data.session_id
            )
        
        if traversal is None and len(df) == 0:
            return outputData(
                question="End of questions", 
                options=["Done"], 
                found=0,
                session_id=data.session_id
            )
        
        if traversal is None and len(df) != 0:
            if len(df) > 1:
                traits = df["Trait1"].dropna().unique().tolist()
                if traits:
                    print(f"Starting trait check. Traits available: {traits}")
                    game_state["trait_check_mode"] = True
                    game_state["current_trait_index"] = 0
                    game_state["traits_to_check"] = traits
                    
                    first_trait = str(traits[0]).strip()
                    return outputData(
                        question=f"{first_trait}?",
                        options=["Yes", "No"],
                        found=0,
                        session_id=data.session_id
                    )
                else:
                    return outputData(
                        question="Can't find!!", 
                        options=["Can't find!!"], 
                        found=-1,
                        session_id=data.session_id
                    )
            elif len(df) == 1:
                found_name = df.iloc[0]["Name"]
                print(f"FOUND: {found_name}")
                return outputData(
                    question="Found!",
                    options=[found_name],
                    found=1,
                    session_id=data.session_id
                )
        
        options = get_options(df, traversal, prev_club_checker)
        print(f"Options: {options}")
        
        while len(options) == 1:
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
                    found=1,
                    session_id=data.session_id
                )
            elif len(df) == 0:
                print("NOT FOUND after auto-skip")
                return outputData(
                    question="Can't find!!", 
                    options=["Can't find!!"], 
                    found=-1,
                    session_id=data.session_id
                )
            
            if traversal is None:
                if len(df) > 1:
                    traits = df["Trait1"].dropna().unique().tolist()
                    if traits:
                        print(f"Starting trait check after auto-skip. Traits: {traits}")
                        game_state["trait_check_mode"] = True
                        game_state["current_trait_index"] = 0
                        game_state["traits_to_check"] = traits
                        
                        first_trait = str(traits[0]).strip()
                        return outputData(
                            question=f"{first_trait}?",
                            options=["Yes", "No"],
                            found=0,
                            session_id=data.session_id
                        )
                return outputData(
                    question="End of questions", 
                    options=["Done"], 
                    found=0,
                    session_id=data.session_id
                )
            
            options = get_options(df, traversal, prev_club_checker)
            print(f"Options after auto-skip: {options}")
        
        return outputData(
            question=traversal.question,
            options=options,
            found=0,
            session_id=data.session_id
        )
        
    except Exception as e:
        import traceback
        print("ERROR in /process:", e)
        traceback.print_exc()
        return outputData(
            question="Backend error",
            options=[],
            found=-1,
            session_id=data.session_id
        )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)