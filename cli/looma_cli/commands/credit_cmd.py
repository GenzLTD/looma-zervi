"""Credit command — enterprise credit checks via QCC (企查查) MCP."""
from __future__ import annotations

import json

import click

from ..common import (
    API_V1,
    echo_status,
    echo_section,
    echo_result,
    http_post,
    qcc_rpc,
)


@click.command()
@click.argument("keyword", required=False)
@click.option("--detail", is_flag=True, help="完整征信报告（含风险、高管、经营数据）")
@click.option("--json", "json_out", is_flag=True, help="JSON 输出")
@click.option("--no-report", is_flag=True, help="不上报到信任层长期记忆体")
def credit(keyword: str, detail: bool, json_out: bool, no_report: bool):
    """🏢 企业征信查询 — 企查查官方数据（直连 QCC MCP，无需登录）

    \b
    支持模糊搜索：输入简称/品牌名/关键词，自动匹配候选企业
    数据来源: 企查查 (QCC) 官方 MCP 接口
    查询维度: 工商信息 / 风险信息 / 经营状况 / 高管信息

    \b
    登录后自动上报:
      使用 looma login 登录后，每次征信查询会自动上报到
      信任层长期记忆体，供 Navigator 在对话中引用。
      使用 --no-report 可跳过上报。

    \b
    示例:
      looma credit 华为           # 2字即可，自动匹配候选
      looma credit 字节跳动        # 模糊品牌名
      looma credit 阿里巴巴 --detail  # 完整征信报告
    """
    if not keyword:
        keyword = click.prompt("请输入企业名称/关键词", type=str)

    company_data = _credit_via_qcc(keyword, detail, json_out)

    # ── Auto-report to trust layer ──
    if company_data and not no_report:
        _report_to_trust_layer(company_data)


def _credit_via_qcc(keyword: str, detail: bool, json_out: bool) -> dict | None:
    """Query directly via QCC MCP (no looma auth needed).

    Step 1: Fuzzy search via get_company_by_query
    Step 2: If multiple candidates, let user pick
    Step 3: Fetch full registration info + optional detail

    Returns company_data dict if successful, None otherwise.
    """

    echo_section(f"Enterprise Credit: {keyword}")
    echo_status("pending", "直连企查查 QCC MCP ...")

    # ── Step 1: Fuzzy search ──
    ok, result, err = qcc_rpc("company", "tools/call", {
        "name": "get_company_by_query",
        "arguments": {"searchKey": keyword},
    })

    if not ok:
        echo_status("error", f"QCC 查询失败: {err}")
        return None

    content = result.get("result", {}).get("content", [])
    search_result: dict = {}
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                search_result = json.loads(item["text"])
            except json.JSONDecodeError:
                pass
            break

    if not search_result:
        echo_status("warn", "未找到匹配企业，请尝试更具体的名称")
        return None

    match_type = search_result.get("匹配结果", "")

    # ── Multiple candidates ──
    companies = search_result.get("企业信息", [])
    if match_type == "多候选" and len(companies) > 1:
        click.echo()
        echo_status("info", f"找到 {len(companies)} 个匹配企业，请选择:")

        for i, c in enumerate(companies):
            name = c.get("企业名称", "?")
            legal = c.get("法定代表人", "")
            status = c.get("登记状态", "")
            capital = c.get("注册资本", "")
            region = c.get("所属地区", "")

            line = f"  [{i + 1}] {name}"
            extras = []
            if legal:
                extras.append(legal)
            if status:
                extras.append(status)
            if capital:
                extras.append(capital)
            if region:
                extras.append(region)
            click.secho(line, bold=True)
            if extras:
                click.secho(f"       {' | '.join(extras)}", fg="bright_black")

        click.echo()
        choice = click.prompt(
            f"请选择 [1-{len(companies)}]",
            type=click.IntRange(1, len(companies)),
            default=1,
            show_default=False,
        )
        selected = companies[choice - 1]
        company_name = selected.get("企业名称", keyword)
        click.echo()

    elif match_type == "多候选" and len(companies) == 1:
        company_name = companies[0].get("企业名称", keyword)

    else:
        # Exact match — search_result might already be the company data
        # or we fall back to direct lookup
        company_name = search_result.get("企业名称", keyword)

    echo_status("ok", "数据来源: 企查查 (QCC) 官方", "实时工商数据")

    # ── Step 2: Fetch registration info ──
    ok2, result2, err2 = qcc_rpc("company", "tools/call", {
        "name": "get_company_registration_info",
        "arguments": {"searchKey": company_name},
    })

    if not ok2:
        echo_status("error", f"详情查询失败: {err2}")
        return None

    content2 = result2.get("result", {}).get("content", [])
    company_data: dict = {}
    for item in content2:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                company_data = json.loads(item["text"])
            except json.JSONDecodeError:
                pass
            break

    if not company_data:
        echo_status("warn", f"未找到「{company_name}」的工商详情")
        return None

    if json_out:
        click.echo(json.dumps(company_data, indent=2, ensure_ascii=False))
        return company_data

    # Display company info
    echo_section("工商信息")
    fields = [
        ("企业名称", "企业名称"),
        ("统一社会信用代码", "信用代码"),
        ("法定代表人", "法定代表人"),
        ("登记状态", "经营状态"),
        ("成立日期", "成立日期"),
        ("注册资本", "注册资本"),
        ("实缴资本", "实缴资本"),
        ("国标行业", "行业"),
        ("所属地区", "地区"),
        ("人员规模", "人员规模"),
        ("参保人数", "参保人数"),
        ("企业简称", "简称"),
        ("英文名", "英文名"),
        ("注册地址", "注册地址"),
    ]
    for key, label in fields:
        v = company_data.get(key, "")
        if v:
            click.secho(f"  {label}: ", nl=False, fg="bright_black")
            click.echo(v)

    if not detail:
        echo_section("快速查询完成")
        click.secho("  提示: 使用 --detail 获取完整征信报告（风险/高管/经营）", fg="bright_black")
        return company_data

    # ── 2. Risk info ──
    echo_section("风险信息")
    ok, result, err = qcc_rpc("risk", "tools/list")
    if ok:
        tools = result.get("result", {}).get("tools", [])
        if tools:
            ok2, result2, err2 = qcc_rpc("risk", "tools/call", {
                "name": tools[0]["name"],
                "arguments": {"searchKey": company_name},
            })
            if ok2:
                risk_content = result2.get("result", {}).get("content", [])
                for item in risk_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        try:
                            risk_data = json.loads(item["text"])
                            echo_status("ok", f"风险数据获取成功", f"{len(json.dumps(risk_data, ensure_ascii=False))} 字符")
                        except json.JSONDecodeError:
                            echo_status("warn", "风险数据解析失败")
                        break
            else:
                echo_status("warn", f"风险查询: {err2}")
        else:
            echo_status("warn", "风险服务暂无可用工具")
    else:
        echo_status("warn", f"风险服务: {err}")

    # ── 3. Executives ──
    echo_section("主要人员")
    ok, result, err = qcc_rpc("executive", "tools/list")
    if ok:
        tools = result.get("result", {}).get("tools", [])
        if tools:
            ok2, result2, err2 = qcc_rpc("executive", "tools/call", {
                "name": tools[0]["name"],
                "arguments": {"searchKey": company_name},
            })
            if ok2:
                exec_content = result2.get("result", {}).get("content", [])
                found = False
                for item in exec_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        try:
                            exec_data = json.loads(item["text"])
                            if isinstance(exec_data, list):
                                for p in exec_data[:5]:
                                    if isinstance(p, dict):
                                        name = p.get("姓名", p.get("name", ""))
                                        title = p.get("职务", p.get("title", ""))
                                        if name:
                                            click.secho(f"  • {name}  {title}", fg="bright_black")
                                            found = True
                            elif isinstance(exec_data, dict):
                                for k, v in list(exec_data.items())[:5]:
                                    click.secho(f"  • {k}: {v}", fg="bright_black")
                                    found = True
                        except json.JSONDecodeError:
                            pass
                        break
                if not found:
                    echo_status("info", "高管数据格式待解析")
            else:
                echo_status("warn", f"高管查询: {err2}")
        else:
            echo_status("warn", "高管服务暂无可用工具")
    else:
        echo_status("warn", f"高管服务: {err}")

    # ── 4. Operation ──
    echo_section("经营状况")
    ok, result, err = qcc_rpc("operation", "tools/list")
    if ok:
        tools = result.get("result", {}).get("tools", [])
        if tools:
            ok2, result2, err2 = qcc_rpc("operation", "tools/call", {
                "name": tools[0]["name"],
                "arguments": {"searchKey": company_name},
            })
            if ok2:
                op_content = result2.get("result", {}).get("content", [])
                for item in op_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        try:
                            op_data = json.loads(item["text"])
                            echo_status("ok", f"经营数据获取成功", f"{len(json.dumps(op_data, ensure_ascii=False))} 字符")
                        except json.JSONDecodeError:
                            echo_status("warn", "经营数据解析失败")
                        break
            else:
                echo_status("warn", f"经营查询: {err2}")
        else:
            echo_status("warn", "经营服务暂无可用工具")
    else:
        echo_status("warn", f"经营服务: {err}")

    echo_section("征信查询完成")
    echo_result("数据来源", "企查查 (QCC) 官方 MCP")
    return company_data


# ---------------------------------------------------------------------------
# Trust layer reporting — 将 CLI 征信查询记录上报到后端信任层
# ---------------------------------------------------------------------------

def _report_to_trust_layer(company_data: dict):
    """Report this credit check to the looma backend trust layer.

    Requires prior login: looma login
    Uses POST /v1/trust/memories with intersection_type=enterprise_credit_check

    This is best-effort: failures are silent (logged to stderr for debugging).
    """
    # Lazy import to avoid circular dependency at module load
    from .auth_cmd import get_auth_header

    auth = get_auth_header()
    if not auth:
        # Not logged in — skip silently (user hasn't opted into trust layer)
        return

    # Build evidence payload from QCC company_data
    evidence = {
        "behavior": {
            "company_name": company_data.get("企业名称", ""),
            "registered_capital": company_data.get("注册资本", ""),
            "credit_code": company_data.get("统一社会信用代码", ""),
            "legal_person": company_data.get("法定代表人", ""),
            "status": company_data.get("登记状态", ""),
            "established": company_data.get("成立日期", ""),
            "industry": company_data.get("国标行业", ""),
            "region": company_data.get("所属地区", ""),
        },
        "channels": ["cli"],
    }

    payload = {
        "intersection_type": "enterprise_credit_check",
        "evidence": evidence,
        "platform": "cli",
        "visibility": "trusted",
    }

    # Use urllib directly to add auth header (http_post doesn't support custom headers)
    import urllib.request
    import sys as _sys

    url = f"{API_V1}/trust/memories"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
                "User-Agent": "Looma-CLI/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201):
                echo_status("ok", "已上报至信任层长期记忆体",
                            company_data.get("企业名称", ""))
    except Exception as e:
        # Best-effort: don't break the UX for reporting failures
        click.secho(f"  [debug] 信任层上报失败: {e}", fg="bright_black", err=True)
