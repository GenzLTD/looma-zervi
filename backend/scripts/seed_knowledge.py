"""Seed the Looma RAG knowledge base with basic PlanetX docs.

Run after the backend is configured (or directly against the data/chroma directory).

Example:
    cd backend
    source .venv/bin/activate
    python scripts/seed_knowledge.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask
from src.config import Config
from src.thomas_core.rag.chroma_client import add_documents


def main():
    app = Flask(__name__)
    app.config.from_object(Config)

    docs = [
        # PlanetX / Looma overview
        "PlanetX 是 Looma 项目打造的星际探索社区，也是年轻人发现自我、连接同频伙伴、提升职业技能的 AI 伴侣平台。"
        "用户可以在这里完成星际人格测评、参与星际问答、获取诗词推荐、探索职业匹配，并与 AI 助手进行对话。"
        "PlanetX 的愿景是：让每个人都能找到属于自己的星际坐标，在六大探索域中持续成长。",

        # What can users explore
        "在 PlanetX 你可以探索以下内容：\n"
        "1. 星际人格测试：8 道精选题，基于特质组合生成你的人格类型。\n"
        "2. 星际问答：向 AI 提问，获取知识库和通用知识回答。\n"
        "3. 诗词推荐：输入心情或场景，推荐一句诗词。\n"
        "4. 职位匹配：上传简历或描述经历，匹配适合的工作。\n"
        "5. 舰队：完成人格测试后可组建或加入 3 人舰队。\n"
        "6. AI 助手：随时对话，获取建议、分析和创意灵感。\n"
        "7. 六域探索：职业域、学习域、生活域、社交域、健康域、创意域，覆盖成长全场景。",

        # PlanetX 六域探索体系
        "PlanetX 六域探索体系是平台核心玩法，包含六个成长域：\n"
        "职业域——简历解析、职位匹配、职业能力分析与职业路径规划；\n"
        "学习域——技能训练、知识问答、AI 辅导与学习路线推荐；\n"
        "生活域——时间管理、生活建议、日常规划与效率提升；\n"
        "社交域——人格匹配、组建舰队、星际社区与寻找同频伙伴；\n"
        "健康域——心理健康、情绪陪伴、作息建议与压力疏导；\n"
        "创意域——诗词推荐、艺术创作、灵感激发与创意写作。\n"
        "每个域都有对应任务和 AI 互动，帮助用户形成可积累的成长轨迹。",

        # 职业域
        "职业域是 PlanetX 六域探索之一。用户可以上传简历或描述工作经历，AI 会解析能力标签并推荐匹配的职位。"
        "职业域还提供职业能力分析、职业路径规划和面试建议，帮助用户发现适合自己的职业方向。"
        "关键词：职业域、职位匹配、找工作、简历解析、职业能力、职业方向、求职。",

        # 学习域
        "学习域是 PlanetX 六域探索之一。用户可以通过技能训练题目检验和提升技能，也可以使用星际问答获取知识讲解。"
        "AI 会根据用户的学习目标和人格特质推荐学习路线。"
        "关键词：学习域、技能训练、答题、知识问答、学习路线、AI 辅导。",

        # 生活域
        "生活域是 PlanetX 六域探索之一。用户可以向 AI 询问时间管理、生活规划、效率提升等建议。"
        "生活域帮助用户把成长落实到日常习惯和具体行动中。"
        "关键词：生活域、时间管理、生活建议、日常规划、效率、习惯。",

        # 社交域
        "社交域是 PlanetX 六域探索之一。完成人格测评后，用户可以组建或加入 3 人舰队，与性格互补的伙伴共同探索。"
        "社交域基于人格匹配算法，帮助用户找到同频伙伴。"
        "关键词：社交域、人格匹配、舰队、同频伙伴、社区、组队。",

        # 健康域
        "健康域是 PlanetX 六域探索之一。用户可以在这里获得心理健康、情绪陪伴、作息建议和压力疏导。"
        "健康域强调身心平衡，是长期成长的基石。"
        "关键词：健康域、心理健康、情绪陪伴、作息、压力疏导、身心平衡。",

        # 创意域
        "创意域是 PlanetX 六域探索之一。用户可以输入心情或场景，获取诗词推荐，也可以向 AI 寻求灵感、创作建议。"
        "创意域涵盖诗词、艺术、写作和创意思维。"
        "关键词：创意域、诗词推荐、艺术创作、灵感、创意写作、创造力。",

        # Personality test explanation
        "PlanetX 星际人格测试共 8 道单选题，每个选项对应一个特质（social、introvert、growth、"
        "wanderer、planner、action、thinker、creative、balance、leader、perfectionist、supporter 等）。"
        "系统统计你所有选择中得分最高的两个特质，组合成 6 种人格之一：星云艺术家、黑洞程序员、"
        "超新星领航员、双星星系守护者、脉冲星修行者、暗物质漫游者。",

        # How to use the AI assistant
        "星际问答支持：问知识概念（如「什么是 PlanetX」）、询问系统功能（「这里有什么」、"
        "「我可以探索什么」）、诗词推荐（「推荐一句表达思念的诗」）、性格/职业探讨（「帮我分析我的性格」）等。"
        "如果知识库没有相关资料，AI 会基于通用知识回答。",

        # Promotion / SEO-friendly summary
        "PlanetX 星际探索社区是什么？它是一个融合人格测评、AI 问答、职业匹配、诗词推荐和团队探索的年轻化平台。"
        "通过六域探索体系（职业域、学习域、生活域、社交域、健康域、创意域），PlanetX 帮助用户发现自己、连接同频伙伴、"
        "提升职业技能，并在 AI 的陪伴下持续成长。欢迎来到 PlanetX，开启你的星际旅程。",
    ]

    metadatas = [
        {"source": "seed", "topic": "overview"},
        {"source": "seed", "topic": "features"},
        {"source": "seed", "topic": "six_domains"},
        {"source": "seed", "topic": "domain_career"},
        {"source": "seed", "topic": "domain_learning"},
        {"source": "seed", "topic": "domain_life"},
        {"source": "seed", "topic": "domain_social"},
        {"source": "seed", "topic": "domain_health"},
        {"source": "seed", "topic": "domain_creative"},
        {"source": "seed", "topic": "personality"},
        {"source": "seed", "topic": "howto"},
        {"source": "seed", "topic": "promotion"},
    ]

    ids = [
        "seed_overview",
        "seed_features",
        "seed_six_domains",
        "seed_domain_career",
        "seed_domain_learning",
        "seed_domain_life",
        "seed_domain_social",
        "seed_domain_health",
        "seed_domain_creative",
        "seed_personality",
        "seed_howto",
        "seed_promotion",
    ]

    with app.app_context():
        add_documents(docs, metadatas=metadatas, ids=ids)
        print(f"Seeded {len(docs)} documents into the knowledge base.")


if __name__ == "__main__":
    main()
