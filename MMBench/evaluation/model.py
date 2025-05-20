import openai
import backoff
import re


completion_tokens = prompt_tokens = 0


# Print error message before each retry
def log_backoff(details):
    print(f"Error occurred: {details['exception']}. Retrying...")


@backoff.on_exception(
    backoff.expo, 
    openai.OpenAIError, 
    max_tries=200, 
    on_backoff=log_backoff  # Call log_backoff before each retry
)
def completions_with_backoff(client, messages, model, temperature, max_tokens, cnt, stop, top_p):
    response = client.chat.completions.create(
        messages=messages, model=model, temperature=temperature,
        max_tokens=max_tokens, n=cnt, stop=stop, top_p=top_p
        )

    return response


def gpt(prompt, base_url="https://api.openai.com/v1", key='', model="gpt-4o", temperature=0.7, max_tokens=2000, n=1, stop=None, top_p=0.9):
    messages = [{"role": "user", "content": prompt}]
    client = openai.Client(api_key=key, base_url=base_url)
    result = generate(client, messages, model, temperature, max_tokens, n, stop,top_p)
    return result


def generate(client, messages, model, temperature=0.7, max_tokens=1000, n=1, stop=None, top_p=1.0):
    global completion_tokens, prompt_tokens
    outputs = []
    while n > 0:
        cnt = min(n, 20)  # A maximum of 20 queries per query
        n -= cnt

        res = completions_with_backoff(client, messages=messages, model=model, temperature=temperature,
                                       max_tokens=max_tokens, cnt=cnt, stop=stop, top_p=top_p)

        # Check the choices in the response and make sure message["content"] exists
        for choice in res.choices:
            try:
                response = choice.message.content

                # Use regular expression matching to ignore case and extra spaces
                pattern = re.compile(r'end\s+of\s+answer\.', re.IGNORECASE)
                match = pattern.search(response)

                if match:
                    end_pos = match.end()
                    response = response[:end_pos]
                
                # New judgment statement: If the regular expression matches the response with "End of answer.", the previous content is returned.
                if re.search(r"End of answer\.", response):
                    response = re.split(r"End of answer\.", response)[0]
                
                # New judgment statement: If more than two "Question:" are matched in the response, the content before the second "Question:" is returned
                matches = list(re.finditer(r"Question:", response))
                if len(matches) >= 2:
                    second_question_pos = matches[1].start()
                    response = response[:second_question_pos]

                ##################################
                outputs.append(response)
            except:
                print(f"Unexpected response format: {choice}")

        # Cumulative token usage
        completion_tokens += res.usage.completion_tokens
        prompt_tokens += res.usage.prompt_tokens
    return outputs


def gpt_usage(backend="gpt-4"):
    global completion_tokens, prompt_tokens
    cost = 0
    if backend == "gpt-4":
        cost = completion_tokens / 1000 * 0.06 + prompt_tokens / 1000 * 0.03
    elif backend == "gpt-4o":
        cost = completion_tokens / 1000 * 0.015 + prompt_tokens / 1000 * 0.005
    elif backend == "gpt-3.5-turbo":
        cost = completion_tokens / 1000 * 0.002 + prompt_tokens / 1000 * 0.0015
    return {"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost}
