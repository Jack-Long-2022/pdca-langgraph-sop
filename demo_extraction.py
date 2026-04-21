"""结构化抽取演示脚本

展示 StructuredExtractor 如何从文本中提取节点、边和状态

运行: python demo_extraction.py
"""

import re
from pdca.plan.extractor import NodeExtractor, EdgeExtractor, StateExtractor

def demo_node_extraction():
    """演示节点提取"""
    print("="*60)
    print("节点提取演示")
    print("="*60)

    # 示例文本
    text = """
    我想创建一个自动化流程：
    首先调用API获取销售数据，然后对数据进行清洗，
    接着分析销售趋势，最后生成报告并发送邮件。
    如果数据不完整，则记录错误并重试。
    """

    print(f"\n输入文本:\n{text}")

    # 提取动词短语
    print(f"\n--- 第一步: 提取动词短语 ---")
    patterns = [
        r'(?:首先|先|第一|接着|然后|之后|随后|最后|最终)([^\n，。！？]+)',
        r'([^\n，。！？]+(?:调用|执行|运行|使用|获取|查询|分析|判断|生成|创建))',
    ]

    phrases = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        phrases.extend(matches)

    print(f"提取到的短语:")
    for i, phrase in enumerate(phrases, 1):
        print(f"  {i}. {phrase}")

    # 关键词分类
    print(f"\n--- 第二步: 关键词分类 ---")

    TOOL_KEYWORDS = ['调用', '执行', '运行', '使用', '获取', '查询', '发送', '上传', '下载',
                      '处理', '转换', '格式化', '验证', '检查', '计算', '存储', '保存']

    THOUGHT_KEYWORDS = ['分析', '思考', '判断', '评估', '总结', '生成', '创建', '设计',
                         '规划', '推理', '理解', '识别', '分类', '提取']

    CONTROL_KEYWORDS = ['开始', '结束', '终止', '跳过', '重试', '循环', '分支',
                         '如果', '当', '则', '否则', '或者']

    print(f"\n节点类型判定:")
    for i, phrase in enumerate(phrases, 1):
        node_type = 'tool'  # 默认

        # 检查控制关键词
        for keyword in CONTROL_KEYWORDS:
            if phrase.startswith(keyword):
                node_type = 'control'
                break

        # 检查思维关键词
        if node_type == 'tool':
            for keyword in THOUGHT_KEYWORDS:
                if keyword in phrase:
                    node_type = 'thought'
                    break

        # 检查工具关键词
        if node_type == 'tool':
            for keyword in TOOL_KEYWORDS:
                if keyword in phrase:
                    node_type = 'tool'
                    break

        # 找到匹配的关键词
        matched_keyword = "默认"
        for keyword_list, type_name in [(TOOL_KEYWORDS, 'tool'),
                                          (THOUGHT_KEYWORDS, 'thought'),
                                          (CONTROL_KEYWORDS, 'control')]:
            for keyword in keyword_list:
                if keyword in phrase:
                    matched_keyword = keyword
                    break

        print(f"  {i}. '{phrase}'")
        print(f"     → 类型: {node_type}")
        print(f"     → 匹配关键词: '{matched_keyword}'")


def demo_edge_extraction():
    """演示边提取"""
    print("\n" + "="*60)
    print("边提取演示")
    print("="*60)

    text = "首先调用API，然后清洗数据，接着分析趋势，最后生成报告。"

    print(f"\n输入文本: {text}")

    # 连接词
    SEQUENTIAL_WORDS = ['然后', '接着', '之后', '随后', '再', '最后', '最终']
    CONDITIONAL_WORDS = ['如果', '当', '只要', '假如', '若是', '要是']

    print(f"\n--- 边连接识别 ---")

    # 查找连接词
    found_connections = []
    for word in SEQUENTIAL_WORDS + CONDITIONAL_WORDS:
        if word in text:
            found_connections.append(word)

    print(f"找到的连接词: {found_connections}")

    # 模拟节点连接
    print(f"\n节点连接关系:")
    nodes = ["调用API", "清洗数据", "分析趋势", "生成报告"]

    for i in range(len(nodes) - 1):
        print(f"  {nodes[i]} --[顺序]--> {nodes[i+1]}")


def demo_state_extraction():
    """演示状态提取"""
    print("\n" + "="*60)
    print("状态提取演示")
    print("="*60)

    text = "获取销售数据的结果，分析销售趋势的列表，统计销售数量"

    print(f"\n输入文本: {text}")

    # 数据模式
    DATA_PATTERNS = [
        (r'([^，,。\n]{1,5})的结果', 'result'),
        (r'([^，,。\n]{1,5})的内容', 'content'),
        (r'([^，,。\n]{1,5})的数据', 'data'),
        (r'([^，,。\n]{1,5})的信息', 'info'),
        (r'([^，,。\n]{1,5})的列表', 'list'),
        (r'([^，,。\n]{1,5})的数量', 'count'),
    ]

    print(f"\n--- 状态字段提取 ---")

    states = []
    for pattern, default_type in DATA_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            field_name = match.strip()

            # 推断类型
            if '数量' in field_name:
                field_type = 'integer'
            elif '列表' in field_name:
                field_type = 'array'
            else:
                field_type = 'string'

            states.append({
                'field_name': field_name,
                'type': field_type,
                'pattern': pattern
            })

    print(f"提取到的状态字段:")
    for state in states:
        print(f"  - {state['field_name']}: {state['type']}")
        print(f"    匹配模式: {state['pattern']}")


def demo_complete_extraction():
    """演示完整的结构化抽取"""
    print("\n" + "="*60)
    print("完整结构化抽取演示")
    print("="*60)

    from pdca.plan.extractor import StructuredExtractor

    # 输入文本
    text = """
    # 销售数据分析工作流

    首先调用销售数据API获取本月销售记录，
    然后对数据进行清洗，处理缺失值和异常值，
    接着分析销售趋势，计算同比增长率，
    最后生成可视化报告并通过邮件发送给相关人员。
    """

    print(f"\n输入文本:\n{text}")

    # 执行抽取
    extractor = StructuredExtractor()
    document = extractor.extract(text)

    print(f"\n--- 抽取结果 ---")
    print(f"节点数: {len(document.nodes)}")
    print(f"边数: {len(document.edges)}")
    print(f"状态数: {len(document.states)}")

    print(f"\n节点列表:")
    for node in document.nodes:
        print(f"  - {node.name} ({node.type})")

    print(f"\n边列表:")
    for edge in document.edges:
        print(f"  - {edge.source} --[{edge.type}]--> {edge.target}")

    print(f"\n状态列表:")
    for state in document.states:
        print(f"  - {state.field_name}: {state.type}")


if __name__ == "__main__":
    # 运行所有演示
    demo_node_extraction()
    demo_edge_extraction()
    demo_state_extraction()
    demo_complete_extraction()

    print("\n" + "="*60)
    print("演示完成！")
    print("="*60)
