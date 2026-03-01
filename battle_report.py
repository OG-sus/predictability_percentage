import json
import numpy as np

def get_stats(data, provider_name):
    lats = [r['latencyMs'] for r in data['results']['results'] if provider_name in r['provider']['id']]
    if not lats: return None
    avg = np.mean(lats)
    std = np.std(lats)
    score = max(0, 100 - (std / avg * 100)) if avg > 0 else 0
    return {"avg": avg, "std": std, "score": score}

try:
    with open('battle_results.json', 'r') as f:
        data = json.load(f)

    openai_stats = get_stats(data, "openai:gpt-4o")
    deepseek_stats = get_stats(data, "deepseek-chat")

    print("\n" + "="*40)
    print(" 🛡️  STABILITY NETWORK: THE BATTLE  🛡️")
    print("="*40)
    
    for name, stats in [("OPENAI GPT-4o", openai_stats), ("DEEPSEEK V3", deepseek_stats)]:
        if stats:
            print(f"\n[{name}]")
            print(f"  Avg Latency:  {stats['avg']:.2f}ms")
            print(f"  Jitter (Std): {stats['std']:.2f}ms")
            print(f"  STABILITY:    {stats['score']:.2f}%")
        else:
            print(f"\n[{name}] - NO DATA (Check Rate Limits)")

    print("\n" + "="*40)
except Exception as e:
    print(f"Error: {e}")