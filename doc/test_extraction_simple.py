"""简单的结构化提取测试 - 不依赖LLM

演示正则表达式和关键词匹配的提取逻辑
"""

import re
import uuid

def extract_nodes_simple(text):
    """简化的节点提取演示"""
    print("\n" + "="*60)
    print("节点提取演示")
    print("="*60)

    # 定义关键词
    TOOL_KEYWORDS = ['调用', '执行', '运行', '使用', '获取', '查询']
    THOUGHT_KEYWORDS = ['分析', '思考', '判断', '评估', '总结', '生成']
    CONTROL_KEYWORDS = ['开始', '结束', '如果', '当', '则', '否则']

    # 提取动词短语
    patterns = [
        r'(?:首先|先|第一|接着|然后|之后|随后|最后|最终)([^\n，。！？]+)',
        r'([^\n，。！？]+(?:调用|执行|运行|使用|获取|查询|分析|判断|生成))',
    ]

    phrases = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        phrases.extend(matches)

    print(f"\n1. 提取到的动词短语:")
    for i, phrase in enumerate(phrases, 1):
        print(f"   {i}. {phrase}")

    # 分类节点
    nodes = []
    for phrase in phrases:
        node_type = 'tool'  # 默认

        if phrase.startswith(tuple(CONTROL_KEYWORDS)):
            node_type = 'control'
        elif any(kw in phrase for kw in THOUGHT_KEYWORDS):
            node_type = 'thought'
        elif any(kw in phrase for kw in TOOL_KEYWORDS):
            node_type = 'tool'

        nodes.append({
            'id': f"node_{uuid.uuid4().hex[:8]}",
            'name': phrase.strip(),
            'type': node_type
        })

    print(f"\n2. 节点分类结果:")
    for node in nodes:
        print(f"   - {node['name'][:30]} → {node['type']}")

    return nodes


def extract_edges_simple(nodes):
    """简化的边提取演示"""
    print("\n" + "="*60)
    print("边提取演示")
    print("="*60)

    edges = []
    # 默认顺序连接
    for i in range(len(nodes) - 1):
        edges.append({
            'source': nodes[i]['id'],
            'target': nodes[i+1]['id'],
            'type': 'sequential'
        })

    print(f"\n生成的边连接:")
    for edge in edges:
        source_name = next(n['name'] for n in nodes if n['id'] == edge['source'])
        target_name = next(n['name'] for n in nodes if n['id'] == edge['target'])
        print(f"   {source_name[:30]} → {target_name[:30]}")

    return edges


def extract_states_simple(text):
    """简化的状态提取演示"""
    print("\n" + "="*60)
    print("状态提取演示")
    print("="*60)

    # 匹配数据对象模式
    patterns = [
        r'([^，,。\n]{1,5})的结果',
        r'([^，,。\n]{1,5})的数据',
        r'([^，,。\n]{1,5})的列表',
    ]

    states = []
    seen = set()

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            field = match.strip()
            if field not in seen:
                seen.add(field)

                # 推断类型
                if '数量' in field or 'count' in field.lower():
                    field_type = 'integer'
                elif '列表' in field or 'list' in field.lower():
                    field_type = 'array'
                else:
                    field_type = 'string'

                states.append({
                    'field_name': field,
                    'type': field_type
                })

    if not states:
        # 默认状态
        states = [
            {'field_name': 'input_text', 'type': 'string'},
            {'field_name': 'result', 'type': 'any'}
        ]

    print(f"\n提取到的状态字段:")
    for state in states:
        print(f"   - {state['field_name']}: {state['type']}")

    return states


def main():
    """主函数"""
    print("="*60)
    print("结构化提取测试 - 不依赖LLM")
    print("="*60)

    # 测试文本
    text = """
    # 销售数据分析工作流

    首先调用API获取销售数据，然后清洗数据，
    接着分析销售趋势，最后生成分析报告。
    如果数据不完整，则记录错误。
    """

    print(f"\n输入文本:")
    print(text)

    # 执行提取
    nodes = extract_nodes_simple(text)
    edges = extract_edges_simple(nodes)
    states = extract_states_simple(text)

    # 输出JSON格式
    print("\n" + "="*60)
    print("最终提取结果 (JSON格式)")
    print("="*60)

    import json
    result = {
        'nodes': nodes,
        'edges': edges,
        'states': states
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)


if __name__ == "__main__":
    main()
