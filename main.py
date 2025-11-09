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

BASE_DIR = Path(__file__).resolve().parent

# Mount static files
app.mount("/frontend", StaticFiles(directory=str(BASE_DIR / "frontend")), name="frontend")

# Load data files
try:
    with open(BASE_DIR / 'Data' / 'questions.json', 'r', encoding='utf-8') as f:
        questions_set = json.load(f)
    mainDf = pd.read_excel(BASE_DIR / 'Data' / 'data.xlsx')
    print(f"✓ Loaded {len(mainDf)} records from data.xlsx")
    print(f"✓ Loaded {len(questions_set)} questions")
except FileNotFoundError as e:
    print(f"ERROR: Could not find data files: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"BASE_DIR: {BASE_DIR}")
    questions_set = {}
    mainDf = pd.DataFrame()
except Exception as e:
    print(f"ERROR loading data: {e}")
    questions_set = {}
    mainDf = pd.DataFrame()

# In-memory session storage
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
    session_id: Optional[str] = None


class outputData(BaseModel):
    question: str
    options: List[str]
    found: int
    session_id: Optional[str] = None


def initializeNodes(questions_set):
    """Initialize question nodes from JSON data"""
    nodes = []
    for i in range(len(questions_set)):
        qid = f"q{i+1}"
        if qid not in questions_set:
            continue
        qdata = questions_set[qid]
        nodes.append(Node(
            questionId=qid,
            question=qdata["question"],
            attribute=qdata["attribute"],
            options=qdata.get("options", []),
            yes=qdata["next_question"].get("yes"),
            no=qdata["next_question"].get("no"),
            default=qdata["next_question"].get("default"),
            checker=qdata.get("checker", [])
        ))
    return nodes


def linkNodes(nodes):
    """Link nodes together based on questionId references"""
    id_map = {node.questionId: node for node in nodes}
    for node in nodes:
        node.yes = id_map.get(node.yes) if node.yes not in ["None", None, ""] else None
        node.no = id_map.get(node.no) if node.no not in ["None", None, ""] else None
        node.default = id_map.get(node.default) if node.default not in ["None", None, ""] else None


# Initialize question tree
nodes = initializeNodes(questions_set) if questions_set else []
if nodes:
    linkNodes(nodes)
    print(f"✓ Initialized {len(nodes)} question nodes")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve main page"""
    index_path = BASE_DIR / "frontend" / "index.html"
    if not index_path.exists():
        return HTMLResponse(content="<h1>Error: index.html not found</h1>", status_code=500)
    return FileResponse(str(index_path))


@app.get("/copyrights.html", response_class=HTMLResponse)
async def copyrights():
    """Serve copyrights page"""
    return FileResponse(str(BASE_DIR / "frontend" / "copyrights.html"))


@app.get("/questions.html", response_class=HTMLResponse)
async def questions_page():
    """Serve questions page"""
    return FileResponse(str(BASE_DIR / "frontend" / "questions.html"))


@app.get("/answers.html", response_class=HTMLResponse)
async def answers_page(name: str = ""):
    """Serve answers page"""
    return FileResponse(str(BASE_DIR / "frontend" / "answers.html"))


@app.post("/reset", response_model=outputData)
def reset_game():
    """Reset game and create new session"""
    session_id = str(uuid.uuid4())
    
    if mainDf.empty or not nodes:
        return outputData(
            question="Error: Data files not loaded properly",
            options=["Please contact administrator"],
            found=-1,
            session_id=session_id
        )
    
    # Create new session
    user_sessions[session_id] = {
        "df": mainDf.copy(),
        "traversal": nodes[0],
        "prev_club_checker": None,
        "trait_check_mode": False,
        "current_trait_index": 0,
        "traits_to_check": []
    }
    
    game_state = user_sessions[session_id]
    
    # Get initial options
    options = []
    for attr in game_state["traversal"].attribute:
        if attr in game_state["df"].columns:
            unique_vals = game_state["df"][attr].dropna().unique().tolist()
            options.extend([str(x).strip() for x in unique_vals if str(x).lower() != 'nan'])
    
    options = sorted(list(set(options)))
    
    if set(options) == {"no", "yes"}:
        options = ["Yes", "No"]
    
    print(f"New session {session_id}: {game_state['traversal'].question}")
    
    return outputData(
        question=game_state["traversal"].question,
        options=options,
        found=0,
        session_id=session_id
    )


def node_traversal(df, temp, traversal, answer, prev_attribute, skip, prev_club_checker):
    """Traverse decision tree and filter dataframe based on answer"""
    answer = answer.strip().lower()
    
    if answer == "yes":
        # Handle club checker
        if traversal.question.startswith("Is your character in") and str(traversal.questionId) != "q8":
            prev_club_checker = traversal.checker[0] if traversal.checker else None
        
        # Filter by checker values
        for attribute in prev_attribute:
            if attribute in df.columns:
                filtered = df[df[attribute].astype(str).str.strip().str.lower().isin(
                    [c.lower() for c in traversal.checker]
                )]
                temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
        df = temp if not temp.empty else df
        traversal = traversal.yes or traversal.default
        
    elif answer == "no":
        # Handle club columns specially
        if prev_attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"]:
            club_columns = ["CLUB", "CLUB2", "CLUB3", "CLUB4"]
            mask = pd.Series([True] * len(df), index=df.index)
            checker_lower = [c.lower() for c in traversal.checker]
            
            for club_col in club_columns:
                if club_col in df.columns:
                    mask &= ~df[club_col].astype(str).str.strip().str.lower().isin(checker_lower)
            df = df[mask]
        else:
            # Regular filtering
            for attribute in prev_attribute:
                if attribute in df.columns:
                    filtered = df[~df[attribute].astype(str).str.strip().str.lower().isin(
                        [c.lower() for c in traversal.checker]
                    )]
                    temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
            df = temp if not temp.empty else df
        
        traversal = traversal.no or traversal.default
        
    else:
        # Handle specific answer (not yes/no)
        if skip:
            traversal = getattr(getattr(traversal, "default", None), "default", None)
        else:
            traversal = getattr(traversal, "default", None)

        for attribute in prev_attribute:
            if attribute not in df.columns:
                continue
                
            if attribute in ["State", "City"]:
                # State/City allows "others" and empty values
                df = df[
                    (df[attribute].astype(str).str.strip().str.lower() == answer.lower()) |
                    (df[attribute].astype(str).str.strip().str.lower() == "others") |
                    (df[attribute].astype(str).str.strip() == '')
                ]
                temp = df
                
            elif prev_attribute == ["DOMAIN", "DOMAIN2", "DOMAIN3"]:
                # Handle multiple domain columns
                domain_columns = ["DOMAIN", "DOMAIN2", "DOMAIN3", "DOMAIN4"]
                for dom_attr in domain_columns:
                    if dom_attr in df.columns:
                        filtered = df[df[dom_attr].astype(str).str.strip().str.lower() == answer.lower()]
                        temp = pd.concat([temp, filtered]).drop_duplicates(ignore_index=True)
            else:
                # Exact match
                df = df[df[attribute].astype(str).str.strip().str.lower() == answer.lower()]
                temp = df
                
        df = temp if not temp.empty else pd.DataFrame()
    
    return (df, traversal, answer, prev_attribute, skip, prev_club_checker)


def get_options(df, traversal, prev_club_checker):
    """Get available options for current question"""
    options = []
    
    if df.empty:
        return []
    
    # Handle domain questions with club context
    if traversal.attribute == ["DOMAIN", "DOMAIN2", "DOMAIN3"]:
        club_domain_pairs = [
            ("CLUB", "DOMAIN"),
            ("CLUB2", "DOMAIN2"),
            ("CLUB3", "DOMAIN3"),
            ("CLUB4", "DOMAIN4")
        ]
        
        tempDomains = []
        
        if prev_club_checker:
            # Get domains for specific club
            for _, row in df.iterrows():
                for club_col, domain_col in club_domain_pairs:
                    if club_col in df.columns and domain_col in df.columns:
                        club_val = str(row[club_col]).lower().strip()
                        domain_val = str(row[domain_col]).strip()
                        
                        if club_val == prev_club_checker.lower() and domain_val and domain_val.lower() != 'nan':
                            if domain_val not in tempDomains:
                                tempDomains.append(domain_val)
            
            options = sorted(tempDomains) if tempDomains else ["No domains found"]
        else:
            # Get all domains
            domain_columns = ["DOMAIN", "DOMAIN2", "DOMAIN3", "DOMAIN4"]
            for attr in domain_columns:
                if attr in df.columns:
                    values = df[attr].dropna().unique().tolist()
                    options.extend([str(x).strip() for x in values if str(x).lower() != 'nan'])
            options = sorted(list(set(options)))
    
    # Handle yes/no questions
    elif traversal.attribute in [["CLUB", "CLUB2", "CLUB3", "CLUB4"], ["CLUB-CHECKER"], ["slc/sdc/cr"]]:
        options = ["Yes", "No"]
    
    # Handle regular attributes
    else:
        for attr in traversal.attribute:
            if attr in df.columns:
                values = df[attr].dropna().unique().tolist()
                options.extend([str(x).strip() for x in values if str(x).lower() != 'nan'])
        options = sorted(list(set(options)))
    
    # Normalize yes/no options
    if set([o.lower() for o in options]) == {"no", "yes"}:
        options = ["Yes", "No"]

    return options


@app.post("/process", response_model=outputData)
def start(data: inputData):
    """Process user answer and return next question"""
    
    # Validate session
    if not data.session_id or data.session_id not in user_sessions:
        return outputData(
            question="Session expired. Please restart the game.",
            options=["Restart"],
            found=-1,
            session_id=None
        )
    
    game_state = user_sessions[data.session_id]
    
    # Validate data loaded
    if not nodes:
        return outputData(
            question="No data available",
            options=["Error: Data files not found"],
            found=-1,
            session_id=data.session_id
        )
    
    # Handle trait checking mode
    if game_state["trait_check_mode"]:
        return handle_trait_check(data, game_state)
    
    # Normal question processing
    return handle_normal_question(data, game_state)


def handle_trait_check(data: inputData, game_state):
    """Handle trait verification questions"""
    df = game_state["df"]
    answer = data.SelectedAnswer.strip().lower()
    current_trait = game_state["traits_to_check"][game_state["current_trait_index"]]
    
    # Filter by trait
    if answer == "yes":
        df = df[df["Trait1"].astype(str).str.strip().str.lower() == current_trait.strip().lower()]
    elif answer == "no":
        df = df[~(df["Trait1"].astype(str).str.strip().str.lower() == current_trait.strip().lower())]
    
    game_state["df"] = df
    
    # Check if found or not found
    if len(df) == 1:
        game_state["trait_check_mode"] = False
        found_name = df.iloc[0]["Name"]
        return outputData(
            question="Found!",
            options=[found_name],
            found=1,
            session_id=data.session_id
        )
    elif len(df) == 0:
        game_state["trait_check_mode"] = False
        return outputData(
            question="Can't find!!",
            options=["Can't find!!"],
            found=-1,
            session_id=data.session_id
        )
    
    # Move to next trait
    game_state["current_trait_index"] += 1
    
    if game_state["current_trait_index"] < len(game_state["traits_to_check"]):
        next_trait = game_state["traits_to_check"][game_state["current_trait_index"]]
        return outputData(
            question=f"{next_trait}?",
            options=["Yes", "No"],
            found=0,
            session_id=data.session_id
        )
    else:
        # All traits checked
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


def handle_normal_question(data: inputData, game_state):
    """Handle normal question flow"""
    traversal = game_state["traversal"]
    df = game_state["df"]
    prev_club_checker = game_state["prev_club_checker"]
    
    try:
        answer = data.SelectedAnswer.strip().lower()
        prev_attribute = traversal.attribute
        skip = False
        
        # Special handling for ECE branch
        if traversal.question == "What is your character's Branch?" and answer == "ece":
            skip = True
        
        temp = pd.DataFrame()
        
        # Update prev_club_checker if selecting a club
        if prev_attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"] and answer == "yes":
            prev_club_checker = traversal.checker[0].lower().strip() if traversal.checker else None
        
        # Traverse and filter
        (df, traversal, answer, prev_attribute, skip, prev_club_checker) = node_traversal(
            df, temp, traversal, answer, prev_attribute, skip, prev_club_checker
        )
        
        # Update game state
        game_state["df"] = df
        game_state["traversal"] = traversal
        game_state["prev_club_checker"] = prev_club_checker
        
        # Check results
        if len(df) == 1:
            found_name = df.iloc[0]["Name"]
            return outputData(
                question="Found!",
                options=[found_name],
                found=1,
                session_id=data.session_id
            )
        elif len(df) == 0:
            return outputData(
                question="Can't find!!",
                options=["Can't find!!"],
                found=-1,
                session_id=data.session_id
            )
        
        # End of questions - start trait checking
        if traversal is None:
            if len(df) > 1:
                traits = df["Trait1"].dropna().unique().tolist()
                if traits:
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
            else:
                return outputData(
                    question="End of questions",
                    options=["Done"],
                    found=0,
                    session_id=data.session_id
                )
        
        # Get options and auto-skip single-option questions
        options = get_options(df, traversal, prev_club_checker)
        
        while len(options) == 1 and options[0] != "No domains found":
            auto_answer = options[0].strip().lower()
            prev_attribute = traversal.attribute
            skip = False
            
            if traversal.question == "What is your character's Branch?" and auto_answer == "ece":
                skip = True
            
            temp = pd.DataFrame()
            
            if prev_attribute == ["CLUB", "CLUB2", "CLUB3", "CLUB4"] and auto_answer not in ["yes", "no"]:
                prev_club_checker = auto_answer.lower().strip()
            
            (df, traversal, auto_answer, prev_attribute, skip, prev_club_checker) = node_traversal(
                df, temp, traversal, auto_answer, prev_attribute, skip, prev_club_checker
            )
            
            game_state["df"] = df
            game_state["traversal"] = traversal
            game_state["prev_club_checker"] = prev_club_checker
            
            if len(df) == 1:
                found_name = df.iloc[0]["Name"]
                return outputData(
                    question="Found!",
                    options=[found_name],
                    found=1,
                    session_id=data.session_id
                )
            elif len(df) == 0:
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
        
        return outputData(
            question=traversal.question,
            options=options,
            found=0,
            session_id=data.session_id
        )
        
    except Exception as e:
        import traceback
        print(f"ERROR in /process: {e}")
        traceback.print_exc()
        return outputData(
            question="Backend error occurred",
            options=["Please restart"],
            found=-1,
            session_id=data.session_id
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "data_loaded": not mainDf.empty,
        "questions_loaded": len(nodes) > 0,
        "active_sessions": len(user_sessions)
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

