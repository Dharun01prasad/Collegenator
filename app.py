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