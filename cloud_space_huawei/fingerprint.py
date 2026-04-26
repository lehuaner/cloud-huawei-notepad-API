"""
华为云空间指纹获取模块
使用 Playwright 执行 JS 获取真实设备指纹
"""

import json
import logging
import hashlib
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

# 指纹存储路径
_FP_STORAGE_PATH = Path(__file__).parent.parent / ".fingerprint.json"


def _xor_encrypt(data: str) -> str:
    """XOR 加密，与 JS 中一致"""
    key = 211
    result = []
    for char in data:
        encrypted_byte = (ord(char) ^ (key - 1)) & 0xFF  # 添加掩码，确保在 0-255 范围内
        result.append(chr(encrypted_byte))
        key = encrypted_byte
    return ''.join(result)


def _base64_encode(data: str) -> str:
    """Base64 编码"""
    import base64
    return base64.b64encode(data.encode('utf-8')).decode('ascii')


def _md5(data: str) -> str:
    """MD5 哈希 - 与 JS 中一致（UTF-8 编码）"""
    return hashlib.md5(data.encode('utf-8')).hexdigest()


def _url_encode(value) -> str:
    """URL 编码，与 JS 中 encodeURIComponent 一致"""
    if value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return quote(str(value), safe='')


def _load_saved_fingerprint() -> str | None:
    """从文件加载已保存的指纹"""
    if not _FP_STORAGE_PATH.exists():
        return None
    try:
        data = json.loads(_FP_STORAGE_PATH.read_text(encoding="utf-8"))
        return data.get("fp")
    except Exception:
        return None


def save_fingerprint(fp: str) -> None:
    """保存指纹到文件"""
    try:
        data = {"fp": fp}
        _FP_STORAGE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[指纹] 已保存指纹到 {_FP_STORAGE_PATH}")
    except Exception as e:
        logger.warning(f"[指纹] 保存指纹失败: {e}")


def get_fingerprint_by_playwright() -> str:
    """
    使用 Playwright 启动浏览器执行 JS 获取真实指纹

    Returns:
        str: 完整的 fp 值（经过 XOR 加密和 Base64 编码）
    """
    with sync_playwright() as p:
        # headless 模式，不显示浏览器窗口
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 直接访问华为登录页面
        page.goto("https://id1.cloud.huawei.com/CAS/portal/cloudIframeLogin.html", timeout=30000)

        # 等待页面加载完成
        page.wait_for_load_state("networkidle", timeout=15000)

        # 执行 JS 获取指纹数据
        fp_data = page.evaluate("""
            (function() {
                // 尝试从 localStorage 获取已存在的 sid
                var sid = '';
                try {
                    sid = localStorage.getItem('hwid_cas_sid') || '';
                } catch(e) {}

                // 构建指纹数据对象
                var h = {
                    canvasData: "",  // canvas 原始数据，用于 Python 计算 MD5
                    webglData: "",   // webgl 原始数据，用于 Python 计算 MD5
                    ips: [],
                    devs: [],
                    epl: 0,
                    ep: "",
                    epls: "",
                    fonts: "",
                    indexid: "",
                    dbsid: "",
                    flashid: "",
                    nacn: navigator.appCodeName || "",
                    nan: navigator.appName || "",
                    nce: navigator.cookieEnabled ? "1" : "0",
                    nlg: navigator.language || "",
                    npf: (navigator.platform || "").split(" ").shift(),
                    sah: screen.availHeight || 0,
                    saw: screen.availWidth || 0,
                    sh: screen.height || 0,
                    sw: screen.width || 0,
                    bsh: document.body.clientHeight || 0,
                    bsw: document.body.clientWidth || 0,
                    ett: Date.now(),
                    etz: new Date().getTimezoneOffset(),
                    localStorage: sid
                };

                // Canvas 指纹 - 返回原始数据，由 Python 计算 MD5
                try {
                    var canvas = document.createElement("canvas");
                    canvas.height = 60;
                    canvas.width = 400;
                    var ctx = canvas.getContext("2d");
                    ctx.textBaseline = "alphabetic";
                    ctx.fillStyle = "#f60";
                    ctx.fillRect(125, 1, 62, 20);
                    ctx.fillStyle = "#069";
                    ctx.font = "11pt no-real-font-123";
                    ctx.fillText("Cwm fjordbank glyphs vext quiz, 😃", 2, 15);
                    ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
                    ctx.font = "18pt Arial";
                    ctx.fillText("Cwm fjordbank glyphs vext quiz, 😃", 4, 45);
                    h.canvasData = canvas.toDataURL();
                } catch(e) {}

                // WebGL 指纹 - 返回原始数据，由 Python 计算 MD5
                try {
                    var canvas = document.createElement("canvas");
                    var gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
                    if (gl) {
                        h.webglData = gl.getParameter(gl.VENDOR) + '~' + gl.getParameter(gl.RENDERER);
                    }
                } catch(e) {}

                return JSON.stringify(h);
            })();
        """)

        browser.close()
        return fp_data


def generate_fp_from_data(data: dict) -> str:
    """
    根据指纹数据生成 fp 值
    与华为服务器加密逻辑一致

    Args:
        data: 指纹数据字典

    Returns:
        str: 加密后的 fp 值
    """
    # 1. 序列化为 key=value，按 key 排序（与 JS 一致）
    pairs = []
    for key in sorted(data.keys()):
        value = data.get(key)
        if value is not None and value != "":
            pairs.append(f"{_url_encode(key)}={_url_encode(value)}")
    serialized = "&".join(pairs)

    # 2. 计算校验和 cs = md5(serialized)
    cs = _md5(serialized)
    data_with_cs = f"{serialized}&cs={cs}"

    # 3. XOR 加密
    encrypted = _xor_encrypt(data_with_cs)

    # 4. Base64 编码
    fp = _base64_encode(encrypted)

    return fp


# 缓存的指纹
_fingerprint_cache: str = None


def get_fingerprint(use_cache: bool = True, force_new: bool = False) -> str:
    """
    获取指纹

    优先级：
    1. 内存缓存（同一进程内）
    2. 文件缓存（已保存的指纹）
    3. 通过 Playwright 获取新指纹

    Args:
        use_cache: 是否使用缓存
        force_new: 是否强制获取新指纹（会覆盖文件缓存）

    Returns:
        str: 加密后的 fp 值
    """
    global _fingerprint_cache

    # 1. 优先使用内存缓存
    if use_cache and not force_new and _fingerprint_cache is not None:
        return _fingerprint_cache

    # 2. 从文件加载已保存的指纹
    if use_cache and not force_new:
        saved_fp = _load_saved_fingerprint()
        if saved_fp:
            logger.info("[指纹] 使用已保存的指纹")
            _fingerprint_cache = saved_fp
            return saved_fp

    # 3. 通过 Playwright 获取新指纹
    logger.info("[指纹] 正在通过 Playwright 获取新指纹...")
    fp_data_json = get_fingerprint_by_playwright()
    raw_data = json.loads(fp_data_json)

    logger.info("[指纹] 获取到指纹数据")

    # 构建与 JS 一致的指纹数据对象
    # canvas 和 webgl 需要计算 MD5
    fp_data = {
        "canvas": _md5(raw_data.get("canvasData", "")),
        "webgl": _md5(raw_data.get("webglData", "")),
        "ips": raw_data.get("ips", []),
        "devs": raw_data.get("devs", []),
        "epl": raw_data.get("epl", 0),
        "ep": raw_data.get("ep", ""),
        "epls": raw_data.get("epls", ""),
        "fonts": raw_data.get("fonts", ""),
        "indexid": raw_data.get("indexid", ""),
        "dbsid": raw_data.get("dbsid", ""),
        "flashid": raw_data.get("flashid", ""),
        "nacn": raw_data.get("nacn", ""),
        "nan": raw_data.get("nan", ""),
        "nce": raw_data.get("nce", ""),
        "nlg": raw_data.get("nlg", ""),
        "npf": raw_data.get("npf", ""),
        "sah": raw_data.get("sah", 0),
        "saw": raw_data.get("saw", 0),
        "sh": raw_data.get("sh", 0),
        "sw": raw_data.get("sw", 0),
        "bsh": raw_data.get("bsh", 0),
        "bsw": raw_data.get("bsw", 0),
        "ett": raw_data.get("ett", 0),
        "etz": raw_data.get("etz", 0),
        "localStorage": raw_data.get("localStorage", "")
    }

    # 生成 fp 值
    fp = generate_fp_from_data(fp_data)
    logger.info(f"[指纹] 新指纹: {fp[:30]}...")

    _fingerprint_cache = fp

    # 4. 保存到文件
    if force_new:
        save_fingerprint(fp)

    return fp


def clear_cache():
    """清除指纹缓存"""
    global _fingerprint_cache
    _fingerprint_cache = None


def clear_saved_fingerprint():
    """删除保存的指纹文件"""
    if _FP_STORAGE_PATH.exists():
        _FP_STORAGE_PATH.unlink()
        logger.info("[指纹] 已删除保存的指纹")


if __name__ == "__main__":
    # 测试
    fp = get_fingerprint(use_cache=False, force_new=True)
    print(f"\n最终 fp: {fp}")
