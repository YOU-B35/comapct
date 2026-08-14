const {Client}=require('ssh2');
const c=new Client();
c.on('ready',()=>{
  const cmd = `
set -e
APP=/opt/autoMedia-social-auto-upload/app
cp -a $APP/sau_backend.py $APP/sau_backend.py.bak.rebind.$(date +%Y%m%d%H%M%S)
python3 <<'PY'
from pathlib import Path
p = Path('/opt/autoMedia-social-auto-upload/app/sau_backend.py')
text = p.read_text(encoding='utf-8')
old_select = '''                SELECT id, type, filePath, userName, status,
                       COALESCE(owner_id, 0),
                       COALESCE(profile_dir, ''),
                       COALESCE(profile_bound_at, ''),
                       COALESCE(proxy_url, ''),
                       COALESCE(proxy_updated_at, '')
                FROM user_info WHERE owner_id = ?'''
new_select = '''                SELECT id, type, filePath, userName, status,
                       COALESCE(owner_id, 0),
                       COALESCE(profile_dir, ''),
                       COALESCE(profile_bound_at, ''),
                       COALESCE(proxy_url, ''),
                       COALESCE(proxy_updated_at, ''),
                       COALESCE(bound_agent_id, ''),
                       COALESCE(bound_agent_hostname, '')
                FROM user_info WHERE owner_id = ?'''
count = text.count(old_select)
if count < 2:
    raise SystemExit(f'expected 2 SELECT blocks, found {count}')
text = text.replace(old_select, new_select)

marker = "@app.route('/login-agent/activate', methods=['POST'])"
if "account_rebind_agent" in text:
    print('rebind route already present')
else:
    if marker not in text:
        raise SystemExit('activate route not found')
    insert = '''

@app.route('/account/<int:account_id>/rebind-agent', methods=['POST'])
@login_required
def account_rebind_agent(account_id: int):
    """把账号绑定到当前（或指定）在线助手，不强制重新扫码。"""
    owner_id = resolve_current_user_id()
    body = request.get_json(silent=True) or {}
    agent_id = str(body.get("agent_id") or "").strip()
    status = agent_status(owner_id)
    if not agent_id:
        agent_id = str((status or {}).get("agent_id") or "").strip()
    if not agent_id or not (status or {}).get("online"):
        return jsonify({"code": 400, "msg": "请先连接并设置当前助手", "data": None}), 400
    agents = list_agents(owner_id)
    target = next((a for a in agents if str(a.get("agent_id") or "") == agent_id), None)
    if not target:
        return jsonify({"code": 404, "msg": "目标助手不在线或不存在", "data": None}), 404
    hostname = str(target.get("hostname") or "").strip()
    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            row = conn.execute(
                "SELECT id FROM user_info WHERE id = ? AND owner_id = ?",
                (int(account_id), owner_id),
            ).fetchone()
            if not row:
                return jsonify({"code": 404, "msg": "账号不存在", "data": None}), 404
            from utils.account_agent_bind import set_account_bound_agent
            set_account_bound_agent(conn, int(account_id), agent_id, hostname)
    except Exception as exc:
        print(f"account_rebind_agent failed: {exc}", flush=True)
        return jsonify({"code": 500, "msg": f"换绑失败: {exc}", "data": None}), 500
    print(
        f"[login-agent] rebind account={account_id} owner={owner_id} "
        f"agent={agent_id} host={hostname}",
        flush=True,
    )
    return jsonify({
        "code": 200,
        "msg": "ok",
        "data": {
            "account_id": int(account_id),
            "bound_agent_id": agent_id,
            "bound_agent_hostname": hostname,
        },
    }), 200


'''
    # insert BEFORE activate route so activate stays, rebind is nearby
    text = text.replace(marker, insert + marker, 1)

p.write_text(text, encoding='utf-8')
print('patched host sau_backend.py ok')
PY

# copy into running container and restart
docker cp $APP/sau_backend.py automedia-social-auto-upload:/app/sau_backend.py
docker restart automedia-social-auto-upload
sleep 6
docker inspect automedia-social-auto-upload --format 'Status={{.State.Status}}'
curl -s -o /dev/null -w 'health=%{http_code} t=%{time_total}\\n' --max-time 10 http://127.0.0.1:18302/ || true
# verify route exists in container
docker exec automedia-social-auto-upload grep -n "account_rebind_agent\\|bound_agent_hostname" /app/sau_backend.py | head -20
`;
  c.exec(cmd,(e,stream)=>{
    let o='';
    stream.on('data',d=>o+=d);
    stream.stderr.on('data',d=>o+=d);
    stream.on('close',(code)=>{console.log(o);c.end();process.exit(code||0);});
  });
}).connect({host:process.env.CROSSHUB_SSH_HOST,username:'root',password:process.env.CROSSHUB_SSH_PASSWORD});
