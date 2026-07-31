from app.browser.manual_chrome import open_manual_frontend_chrome, find_chrome_executable
from app.browser.context import close_temu_runtime, close_tenant_profile_browsers
import time

tenant_id = 5
close_temu_runtime(tenant_id)
close_tenant_profile_browsers(tenant_id)
time.sleep(2)
# Prefer homepage; login.html under automation profile often hits bgn_no_access
url = "https://www.temu.com/"
opened = open_manual_frontend_chrome(tenant_id, url, release_playwright=True)
print("chrome=", find_chrome_executable())
print("opened=", opened)
