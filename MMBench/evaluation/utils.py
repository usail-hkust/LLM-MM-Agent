import json


def load_json(file_path):
    """
    load json data
    
    Args:
        file_path (str): the file path
        
    Returns:
        dict: json data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: File {file_path} not in valid JSON format.")
        return {}



def load_solution_json(file_path):
    """
    Load solution data

    Args:
        file_path (str): the file path

    Returns:
        dict: solution data in json format
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tasks = data.get('tasks', [])
        task_dict = {f"task{i+1}": task for i, task in enumerate(tasks)}

        result = {}
        result.update(task_dict)
        
        return result
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: File {file_path} not in valid JSON format.")
        return {}