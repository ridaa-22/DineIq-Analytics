/* DineIQ application views; values come from authenticated FastAPI endpoints. */
(function () {
  const API = location.port === '8000' ? '' : 'http://127.0.0.1:8000';
  const token = localStorage.getItem('authToken');
  if (!token) { location.replace('Login.html'); return; }
  let profile = {};
  try { profile = JSON.parse(localStorage.getItem('user') || '{}'); } catch (_) { profile = {}; }
  const roles = profile.roles || [];
  const esc = x => String(x == null ? 'N/A' : x).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = x => typeof x === 'number' ? x.toLocaleString(undefined, {maximumFractionDigits: 2}) : esc(x);
  const money = x => 'PKR ' + num(x);
  const view = document.querySelector('.content-wrapper');
  const params = new URLSearchParams(location.search);
  const q = o => new URLSearchParams(Object.entries(o).filter(([,v]) => v !== '' && v != null)).toString();
  async function request(path, options = {}) {
    const response = await fetch(API + path, {...options, headers: {'Authorization':'Bearer ' + token,
      'Content-Type':'application/json', ...(options.headers || {})}});
    if (response.status === 401) { localStorage.removeItem('authToken'); location.replace('Login.html'); throw new Error('Session expired'); }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `API error ${response.status}`);
    return body;
  }
  const card = (label, value) => `<div class="col-sm-6 col-lg-3 grid-margin stretch-card"><div class="card"><div class="card-body"><p class="text-muted">${esc(label)}</p><h3>${esc(value)}</h3></div></div></div>`;
  const panel = (title, body) => `<div class="card mb-4"><div class="card-body"><h4>${esc(title)}</h4>${body}</div></div>`;
  const table = (columns, rows) => !rows?.length ? '<p>No records in this scope.</p>' :
    `<div class="table-responsive"><table class="table table-hover"><thead><tr>${columns.map(([label]) => `<th>${esc(label)}</th>`).join('')}</tr></thead><tbody>` +
    rows.map(row => `<tr>${columns.map(([,key,format]) => `<td>${esc(format ? format(row[key]) : num(row[key]))}</td>`).join('')}</tr>`).join('') + '</tbody></table></div>';
  const links = `<nav class="mb-4"><a class="btn btn-sm btn-outline-light m-1" href="index.html">Executive</a><a class="btn btn-sm btn-outline-light m-1" href="operations-orders.html">Orders</a><a class="btn btn-sm btn-outline-light m-1" href="Menu-management.html">Menu</a><a class="btn btn-sm btn-outline-light m-1" href="customer-segments.html">Customers</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=churn">Churn</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=wastage">Wastage</a><a class="btn btn-sm btn-outline-light m-1" href="analytics-ml.html">Forecast & Models</a>${roles.includes('REGIONAL_MANAGER') && !roles.includes('ADMIN') ? '' : '<a class="btn btn-sm btn-outline-light m-1" href="index.html?view=basket">Basket</a>'}<a class="btn btn-sm btn-outline-light m-1" href="index.html?view=pricing">Pricing</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=promotions">Promotions</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=channels">Channels</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=locations">Locations</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=anomalies">Anomalies</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=rating-anomalies">Rating flags</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=recommendations">Recommendations</a><a class="btn btn-sm btn-outline-light m-1" href="index.html?view=what-if">What-If</a>${roles.includes('REGIONAL_MANAGER') && !roles.includes('ADMIN') ? '' : '<a class="btn btn-sm btn-outline-light m-1" href="reports.html">Reports</a>'}<a class="btn btn-sm btn-outline-light m-1" href="index.html?view=jobs">Jobs</a>${roles.includes('ADMIN') || roles.includes('MANAGER') ? '<a class="btn btn-sm btn-outline-light m-1" href="index.html?view=admin">Manage</a>' : ''}<button class="btn btn-sm btn-outline-danger m-1" id="dineiq-logout">Sign out</button></nav>`;
  const title = (name, note='') => links + `<h2>${esc(name)}</h2><p class="text-muted">${esc(note)}</p>`;
  document.addEventListener('click', async e => { if (e.target.id === 'dineiq-logout') { try { await request('/api/auth/logout',{method:'POST'}); } finally { localStorage.removeItem('authToken'); localStorage.removeItem('user'); location.href='Login.html'; } } });
  async function locationSelect() {
    const locations = await request('/api/locations');
    return `<label for="location-filter">Location</label><select class="form-control col-md-4 mb-3" id="location-filter"><option value="">All assigned locations</option>${locations.map(r => `<option value="${r.location_id}" ${String(r.location_id) === params.get('location_id') ? 'selected' : ''}>${esc(r.location_name)}</option>`).join('')}</select>`;
  }
  async function showDashboard() {
    const location_id = params.get('location_id') || '';
    const [data, select] = await Promise.all([request('/api/dashboard/executive?' + q({location_id})), locationSelect()]);
    view.innerHTML = title('Executive Dashboard', 'Completed transactions from cleaned phase1-v1 data') + select + '<div class="row">' +
      card('Net revenue', money(data.revenue)) + card('Contribution', money(data.contribution)) +
      card('Completed orders', num(data.orders)) + card('AOV', money(data.aov)) +
      card('Active customers', num(data.active_customers)) + card('Repeat customers', num(data.repeat_customers)) +
      card('Wastage cost', money(data.wastage_cost)) + '</div>';
    bindLocation();
  }
  function bindLocation() { const el = document.getElementById('location-filter'); if (el) el.onchange = () => { const url = new URL(location.href); el.value ? url.searchParams.set('location_id', el.value) : url.searchParams.delete('location_id'); location.href = url; }; }
  async function showMenu() {
    const location_id = params.get('location_id') || '';
    const category_id = params.get('category_id') || '';
    const classification = params.get('classification') || '';
    const [data, categories, select] = await Promise.all([request('/api/analytics/menu?' + q({location_id,category_id,classification,limit:150})), request('/api/menu/categories'), locationSelect()]);
    view.innerHTML = title('Menu Intelligence', data.method) + select +
      `<label for="category-filter">Category</label><select class="form-control col-md-4 mb-3" id="category-filter"><option value="">All</option>${categories.map(row => `<option value="${row.category_id}" ${String(row.category_id) === category_id ? 'selected' : ''}>${esc(row.category_name)}</option>`).join('')}</select>` +
      `<label for="class-filter">Classification</label><select class="form-control col-md-4 mb-3" id="class-filter">${['','Profit Driver','Volume Driver','Hidden Opportunity','Low Performer'].map(x => `<option value="${esc(x)}" ${x === classification ? 'selected' : ''}>${esc(x || 'All')}</option>`).join('')}</select>` +
      panel(`${data.total} items`, table([['Item','Item_Name'],['Sales','sales'],['Net revenue','revenue',money],['Contribution','contribution',money],['Profit %','profit_percent'],['Rating','Average_Rating'],['Wastage units','wastage_quantity'],['Class','classification'],['History','insufficient_history',x => x ? 'Insufficient' : 'Established']], data.items));
    bindLocation(); document.getElementById('class-filter').onchange = e => { const url = new URL(location.href); e.target.value ? url.searchParams.set('classification',e.target.value) : url.searchParams.delete('classification'); location.href = url; };
    document.getElementById('category-filter').onchange = e => { const url = new URL(location.href); e.target.value ? url.searchParams.set('category_id',e.target.value) : url.searchParams.delete('category_id'); location.href = url; };
  }
  async function showCustomers() {
    const location_id = params.get('location_id') || '';
    const segment = params.get('segment') || '';
    const [data, profiles, select] = await Promise.all([request('/api/analytics/customers?' + q({location_id,segment,limit:100})),
      request('/api/analytics/customers/profiles?' + q({location_id})), locationSelect()]);
    view.innerHTML = title('Customer Intelligence', data.method) + select +
      `<label for="segment-filter">Segment</label><select class="form-control col-md-4 mb-3" id="segment-filter"><option value="">All</option>${Object.keys(data.segment_counts || {}).map(name => `<option value="${esc(name)}" ${name === segment ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select>` + '<div class="row">' +
      Object.entries(data.segment_counts || {}).map(([name,n]) => card(name,num(n))).join('') + '</div>' +
      panel('Cluster profiles',table([['Cluster','Cluster'],['Business segment','Segment'],['Customers','size'],['Average recency','average_recency'],['Average orders','average_frequency'],['Average net monetary','average_monetary',money]],profiles.profiles)) +
      panel(`${data.total} customers`, table([['Customer','Customer_ID'],['Segment','segment'],['Recency days','recency_days'],['Unique orders','frequency'],['Net monetary','monetary',money]], data.customers));
    bindLocation(); document.getElementById('segment-filter').onchange = e => { const url = new URL(location.href); e.target.value ? url.searchParams.set('segment',e.target.value) : url.searchParams.delete('segment'); location.href = url; };
  }
  async function showOrders() {
    const filters = {location_id:params.get('location_id') || '', date_from:params.get('date_from') || '',
      date_to:params.get('date_to') || '', channel:params.get('channel') || '', status:params.get('status') || '',
      offset:Math.max(0,Number(params.get('offset') || 0)),limit:50};
    const [data, select] = await Promise.all([request('/api/analytics/orders?' + q(filters)),locationSelect()]);
    view.innerHTML = title('Operations & Orders','Historical validated orders; this is not a live kitchen queue') + select +
      `<div class="row mb-3"><div class="col-md-3"><label>From</label><input id="orders-from" class="form-control" type="date" value="${esc(filters.date_from)}"></div><div class="col-md-3"><label>To</label><input id="orders-to" class="form-control" type="date" value="${esc(filters.date_to)}"></div><div class="col-md-3"><label>Channel</label><select id="orders-channel" class="form-control">${['','Dine-in','Takeaway','App','Third-Party Delivery'].map(x => `<option value="${esc(x)}" ${x === filters.channel ? 'selected' : ''}>${esc(x || 'All')}</option>`).join('')}</select></div><div class="col-md-3"><label>Status</label><select id="orders-status" class="form-control">${['','Completed','Cancelled'].map(x => `<option value="${esc(x)}" ${x === filters.status ? 'selected' : ''}>${esc(x || 'All')}</option>`).join('')}</select></div></div><button id="orders-apply" class="btn btn-primary mb-3">Apply filters</button>` +
      '<div class="row">' + card('Matching orders',num(data.total)) + Object.entries(data.status_counts || {}).map(([name,count]) => card(name,num(count))).join('') + '</div>' +
      panel('Orders',table([['Order ID','Order_ID'],['Date/time','Order_DateTime'],['Customer','Customer_ID'],['Location','Location_ID'],['Channel','Channel'],['Status','Order_Status'],['Net revenue','Net_Revenue',x => x == null ? 'N/A' : money(x)]],data.orders) +
        `<p class="text-muted">${esc(data.revenue_note)}</p><button class="btn btn-sm btn-outline-light mr-2" id="orders-prev" ${filters.offset === 0 ? 'disabled' : ''}>Previous</button><span>${num(filters.offset + 1)}–${num(Math.min(filters.offset + 50,data.total))} of ${num(data.total)}</span><button class="btn btn-sm btn-outline-light ml-2" id="orders-next" ${filters.offset + 50 >= data.total ? 'disabled' : ''}>Next</button>`);
    bindLocation();
    const update = changes => { const url=new URL(location.href); Object.entries(changes).forEach(([key,value]) => value ? url.searchParams.set(key,value) : url.searchParams.delete(key)); location.href=url; };
    document.getElementById('orders-apply').onclick = () => update({date_from:document.getElementById('orders-from').value,date_to:document.getElementById('orders-to').value,channel:document.getElementById('orders-channel').value,status:document.getElementById('orders-status').value,offset:''});
    document.getElementById('orders-prev').onclick = () => update({offset:String(Math.max(0,filters.offset-50))});
    document.getElementById('orders-next').onclick = () => update({offset:String(filters.offset+50)});
  }
  async function showWastage() {
    const location_id = params.get('location_id') || '';
    const [data, forecast, history, select] = await Promise.all([request('/api/analytics/wastage?' + q({location_id})),
      request('/api/analytics/wastage/forecast?' + q({location_id,risk:'HIGH',limit:30})),
      request('/api/wastage/records?' + q({location_id,limit:25})), locationSelect()]);
    view.innerHTML = title('Wastage Intelligence',data.prediction_status) + select + '<div class="row">' +
      card('Wastage cost',money(data.total_cost)) + card('Wasted units',num(data.total_quantity)) + '</div>' +
      panel('High wastage items',table([['Item ID','Item_ID'],['Units','quantity'],['Cost','cost',money]],data.high_wastage_items)) +
      panel('Locations',table([['Location ID','Location_ID'],['Cost','Cost_Impact',money]],data.locations)) +
      panel('Clean historical records',table([['Item','Item_ID'],['Location','Location_ID'],['Date','Wastage_Date'],
        ['Quantity','Quantity_Wasted'],['Cost','Cost_Impact',money],['Reason','Reason']],history.records)) +
      panel('Next-week high-risk estimates',`<p>Experimental model; holdout MAE ${num(forecast.metrics.mae)}, baseline MAE ${num(forecast.metrics.baseline_mae)}, high-risk recall ${num(100 * forecast.metrics.high_risk_recall)}%.</p>` +
        table([['Week','Week'],['Item','Item_ID'],['Location','Location_ID'],['Expected units','Expected_Wastage'],['Risk','Risk']],forecast.predictions)); bindLocation();
  }
  async function showModels() {
    const location_id = params.get('location_id') || '';
    const [data, select] = await Promise.all([request('/api/models/comparison?' + q({location_id,limit:150})), locationSelect()]);
    view.innerHTML = title('Spark vs Python Forecast','Same unseen location-day cases; fixed 50-unit agreement tolerance') + select +
      '<div class="row">' + card('Cases',num(data.total)) + card('Spark MAE',num(data.summary.spark_mae)) +
      card('Python MAE',num(data.summary.python_mae)) + card('Agreement',num(data.summary.agreement_percentage) + '%') + '</div>' +
      '<button class="btn btn-primary mb-3" id="predict-next">Predict next day for selected location</button><div id="next-prediction"></div>' + panel('Holdout predictions',table([
        ['Case','Case_ID'],['Actual','Actual'],['Spark','Spark_Prediction'],['Python','Python_Prediction'],['Difference','Difference'],['Match','Match_Status'],['Spark version','Spark_Model_Version'],['Python version','Python_Model_Version']],data.forecasts)); bindLocation();
    document.getElementById('predict-next').onclick = async () => { const locationId = document.getElementById('location-filter').value; const target = document.getElementById('next-prediction'); if (!locationId) { target.textContent='Select a location first.'; return; } try { const result=await request('/api/models/forecast/predict?location_id='+encodeURIComponent(locationId),{method:'POST'}); target.innerHTML=panel('Next-day estimate',`<p>${esc(result.forecast_date)}: ${num(result.prediction)} demand units, ${esc(result.model_version)}. Estimate; actual unavailable.</p>`); } catch(error) { target.textContent=error.message; } };
  }
  async function showWhatIf() {
    view.innerHTML = title('What-If Analysis','Estimates based on observed item economics and your demand assumption') +
      panel('Scenario',`<form id="scenario-form"><div class="row">${[['item_id','Item ID','1'],['location_id','Location ID (optional)',''],['price_change_percent','Price change %','0'],['discount_change_percent','Discount change %','0'],['promotion_discount_percent','New promotion discount % (optional)',''],['demand_change_percent','Demand change %','0'],['preparation_change_percent','Preparation change %','0']].map(([key,label,value]) => `<div class="col-md-4 mb-3"><label>${label}</label><input class="form-control" type="number" step="any" name="${key}" value="${value}"></div>`).join('')}</div><button class="btn btn-primary">Estimate</button></form><div id="scenario-result" class="mt-3"></div>`);
    document.getElementById('scenario-form').onsubmit = async e => { e.preventDefault(); const payload = Object.fromEntries(new FormData(e.target)); Object.keys(payload).forEach(k => payload[k] = payload[k] === '' ? null : Number(payload[k]));
      const target = document.getElementById('scenario-result'); target.textContent='Calculating...'; try { const data = await request('/api/what-if',{method:'POST',body:JSON.stringify(payload)}); target.innerHTML = '<div class="row">' + card('Baseline revenue',money(data.baseline.revenue)) + card('Scenario revenue',money(data.scenario.revenue)) + card('Revenue delta',money(data.delta.revenue)) + card('Contribution delta',money(data.delta.contribution)) + (data.delta.wastage_units == null ? '' : card('Estimated wastage delta',num(data.delta.wastage_units))) + '</div><p>ESTIMATE. Demand response is supplied by the user; causal price effects are not inferred.</p>'; } catch(error) { target.textContent=error.message; } };
  }
  async function showSimple(path, heading, columns, field) {
    const location_id = params.get('location_id') || '';
    const scoped = !path.endsWith('/basket');
    const [data, select] = await Promise.all([request(path + (scoped ? '?' + q({location_id}) : '')),
      scoped ? locationSelect() : Promise.resolve('')]);
    view.innerHTML = title(heading, data.method || '') + select + panel(heading, table(columns, data[field]));
    bindLocation();
  }
  async function showReports() {
    const names = [['Menu intelligence','menu'],['Customer RFM','customers'],['Forecast comparison','forecast'],['Basket associations','basket'],['Wastage','wastage'],['Promotion economics','promotions']];
    const select = await locationSelect();
    view.innerHTML = title('Authenticated Reports','Current cleaned analytics in CSV or Excel; exports are audited') + select + panel('Reports', names.map(([label,slug]) => `<div>${esc(label)} <button class="btn btn-outline-light m-1" data-report="${slug}" data-format="csv">CSV</button><button class="btn btn-outline-light m-1" data-report="${slug}" data-format="xlsx">Excel</button></div>`).join(''));
    bindLocation();
    document.querySelectorAll('[data-report]').forEach(button => button.onclick = async () => { try { const format=button.dataset.format; const scope=q({format,location_id:params.get('location_id') || ''}); const response = await fetch(API + '/api/exports/' + button.dataset.report + '?' + scope,{headers:{Authorization:'Bearer ' + token}}); if (!response.ok) throw new Error('Report unavailable or forbidden'); const blob=await response.blob(); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=button.dataset.report+'.'+format; a.click(); URL.revokeObjectURL(a.href); } catch(error) { alert(error.message); } });
  }
  async function showJobs() {
    const [jobs, models] = await Promise.all([request('/api/jobs'), request('/api/models/versions')]);
    view.innerHTML = title('Processing Jobs & Models','Recorded local runs and model versions') +
      (roles.includes('ADMIN') ? `<div class="mb-3"><select id="job-type" class="form-control col-md-4 d-inline-block"><option value="spark_sql">Spark SQL</option><option value="spark_forecast">Spark forecast</option><option value="basket_rules">Basket rules</option><option value="customer_segments">Customer segments</option><option value="wastage_forecast">Wastage forecast</option></select><button id="start-job" class="btn btn-primary ml-2">Run job</button><span id="job-live" class="ml-2"></span></div>` : '') +
      panel('Jobs',table([['ID','id'],['Job','job_name'],['Status','status'],['Dataset','dataset_version'],['Ended','ended_at']],jobs)) +
      panel('Models',table([['Model','model_name'],['Version','version'],['Algorithm','algorithm'],['Dataset','dataset_version']],models));
    const start = document.getElementById('start-job');
    if (start) start.onclick = async () => { const target=document.getElementById('job-live'); start.disabled=true;
      try { const created=await request('/api/jobs',{method:'POST',body:JSON.stringify({job_name:document.getElementById('job-type').value})});
        target.textContent=`Job ${created.job_id}: QUEUED`;
        const poll=async () => { const job=await request('/api/jobs/'+created.job_id); target.textContent=`Job ${job.id}: ${job.status}`;
          if (job.status === 'QUEUED' || job.status === 'RUNNING') setTimeout(poll,2000); else { start.disabled=false; await showJobs(); } }; setTimeout(poll,2000);
      } catch(error) { target.textContent=error.message; start.disabled=false; } };
  }
  async function showAdmin() {
    const isAdmin = roles.includes('ADMIN');
    const [locations, categories, items, prices, promotions, inventory, wastage, users, audit] = await Promise.all([
      request('/api/locations'),request('/api/menu/categories'),request('/api/menu/items'),request('/api/pricing/history'),
      request('/api/promotions'),request('/api/inventory?limit=25'),request('/api/wastage/records?limit=25'),
      isAdmin ? request('/api/users') : Promise.resolve([]),isAdmin ? request('/api/audit-logs?limit=25') : Promise.resolve([])]);
    const specs = [
      {name:'location',title:'Restaurant locations',path:'/api/locations',id:'location_id',data:locations,
       columns:[['ID','location_id'],['Name','location_name'],['City','city'],['Active','is_active']],
       fields:[['location_name','Name','text'],['city','City','text'],['address','Address','text'],['is_active','Active','boolean']]},
      {name:'category',title:'Menu categories',path:'/api/menu/categories',id:'category_id',data:categories,
       columns:[['ID','category_id'],['Name','category_name']],fields:[['category_name','Name','text']]},
      {name:'item',title:'Menu items',path:'/api/menu/items',id:'item_id',data:items,
       columns:[['ID','item_id'],['Name','item_name'],['Category','category_id'],['Price','base_price'],['Cost','cost']],
       fields:[['item_name','Name','text'],['category_id','Category ID','number'],['base_price','Price','number'],['cost','Cost','number'],['description','Description','text'],['is_available','Available','boolean']]},
      {name:'promotion',title:'Promotions',path:'/api/promotions',id:'promotion_id',data:promotions,
       columns:[['ID','promotion_id'],['Name','promotion_name'],['Discount %','discount_percent'],['Start','start_date'],['End','end_date']],
       fields:[['promotion_name','Name','text'],['discount_percent','Discount %','number'],['start_date','Start','date'],['end_date','End','date'],['applicable_item_id','Item ID (optional)','number'],['applicable_category_id','Category ID (optional)','number']]},
      {name:'inventory',title:'Inventory',path:'/api/inventory',id:'inventory_id',data:inventory.records,
       columns:[['ID','inventory_id'],['Location','location_id'],['Item','item_id'],['Stock','stock_quantity'],['Reorder','reorder_level']],
       fields:[['location_id','Location ID','number'],['item_id','Item ID','number'],['stock_quantity','Stock','number'],['reorder_level','Reorder level','number'],['opening_stock','Opening','number'],['received_quantity','Received','number'],['consumed_quantity','Consumed','number'],['wasted_quantity','Wasted','number'],['period_start','Period start','date'],['period_end','Period end','date']]},
      {name:'wastage',title:'Managed wastage records',path:'/api/wastage/records',id:'id',data:wastage.managed_records,
       columns:[['ID','id'],['Item','item_id'],['Location','location_id'],['Date','wastage_date'],['Units','quantity_wasted']],
       fields:[['item_id','Item ID','number'],['location_id','Location ID','number'],['wastage_date','Date','date'],['quantity_wasted','Units','number'],['cost_impact','Cost impact','number'],['reason','Reason','text']]}
    ];
    if (!isAdmin) specs.shift();
    if (isAdmin) specs.unshift({name:'user',title:'Users',path:'/api/users',data:users,
      columns:[['ID','id'],['Name','username'],['Email','email'],['Roles','roles'],['Active','is_active']],
      fields:[['username','Name','text'],['email','Email','email'],['password','Password','password'],['role','Role','text'],['location_ids','Location IDs, comma separated','list']]});
    const form = spec => `<form id="manage-${spec.name}" class="mb-3">${spec.id ? `<div class="mb-2"><label>${esc(spec.title)} ID to edit (leave blank to add)</label><input class="form-control" name="__id" type="number"></div>` : ''}<div class="row">${spec.fields.map(([key,label,type]) => `<div class="col-md-4 mb-2"><label>${esc(label)}</label>${type === 'boolean' ? `<select class="form-control" name="${key}"><option value="true">Yes</option><option value="false">No</option></select>` : `<input class="form-control" name="${key}" type="${type === 'list' ? 'text' : type}" step="${type === 'number' ? 'any' : ''}">`}</div>`).join('')}</div><button class="btn btn-primary">Save ${esc(spec.title)}</button><span class="ml-2" id="manage-${spec.name}-result"></span></form>`;
    view.innerHTML = title('Management','Changes are audited; historical analytics require a pipeline refresh') +
      specs.map(spec => panel(spec.title,form(spec) + table(spec.columns,spec.data.slice(0,25)))).join('') +
      panel('Clean historical wastage sample',table([['ID','Wastage_ID'],['Item','Item_ID'],['Location','Location_ID'],['Date','Wastage_Date'],['Units','Quantity_Wasted']],wastage.records)) +
      (isAdmin ? panel('Change user role',`<form id="manage-role"><div class="row"><div class="col-md-3"><input class="form-control" name="user_id" type="number" placeholder="User ID"></div><div class="col-md-3"><select class="form-control" name="role"><option>ADMIN</option><option>MANAGER</option><option>REGIONAL_MANAGER</option><option>ANALYST</option></select></div><div class="col-md-3"><input class="form-control" name="location_ids" placeholder="Location IDs, comma separated"></div><div class="col-md-3"><select class="form-control" name="is_active"><option value="true">Active</option><option value="false">Disabled</option></select></div></div><button class="btn btn-primary mt-2">Update role</button><span id="manage-role-result" class="ml-2"></span></form>`) + panel('Recent audit',table([['Action','action'],['Entity','entity'],['ID','entity_id'],['Time','timestamp']],audit)) : '') +
      panel('Recent price history',table([['Item','item_id'],['Price','price'],['Effective','effective_date']],prices.slice(0,25)));
    specs.forEach(spec => { document.getElementById('manage-'+spec.name).onsubmit = async event => { event.preventDefault();
      const values=Object.fromEntries(new FormData(event.target)); const id=values.__id; delete values.__id;
      spec.fields.forEach(([key,,type]) => { if (type === 'number') values[key]=values[key] === '' ? null : Number(values[key]);
        else if (type === 'boolean') values[key]=values[key] === 'true';
        else if (type === 'list') values[key]=values[key] ? values[key].split(',').map(x => Number(x.trim())) : []; });
      const result=document.getElementById('manage-'+spec.name+'-result'); result.textContent='Saving...';
      try { await request(spec.path+(id ? '/'+encodeURIComponent(id) : ''),{method:id?'PUT':'POST',body:JSON.stringify(values)}); result.textContent='Saved. Refreshing...'; setTimeout(showAdmin,500); }
      catch(error) { result.textContent=error.message; } }; });
    const roleForm=document.getElementById('manage-role'); if (roleForm) roleForm.onsubmit=async event => { event.preventDefault();
      const values=Object.fromEntries(new FormData(event.target)); const id=values.user_id; delete values.user_id;
      values.location_ids=values.location_ids ? values.location_ids.split(',').map(x => Number(x.trim())) : [];
      values.is_active=values.is_active === 'true'; const result=document.getElementById('manage-role-result');
      try { await request('/api/users/'+encodeURIComponent(id)+'/role',{method:'PUT',body:JSON.stringify(values)}); result.textContent='Saved'; setTimeout(showAdmin,500); }
      catch(error) { result.textContent=error.message; } };
  }
  document.addEventListener('DOMContentLoaded', async () => {
    if (!view) return;
    const path = location.pathname.split('/').pop().toLowerCase();
    const page = params.get('view') || ({'index.html':'dashboard','operations-orders.html':'orders','menu-management.html':'menu','customer-segments.html':'customers','analytics-ml.html':'models','reports.html':'reports'}[path]);
    const handlers = {dashboard:showDashboard,orders:showOrders,menu:showMenu,customers:showCustomers,wastage:showWastage,models:showModels,'what-if':showWhatIf,reports:showReports,jobs:showJobs,admin:showAdmin,
      basket: () => showSimple('/api/analytics/basket','Market Basket',[['Item','Antecedent_Item_ID'],['Pair item','Consequent_Item_ID'],['Support','Support'],['Confidence','Confidence'],['Lift','Lift']],'rules'),
      pricing: () => showSimple('/api/analytics/pricing','Pricing History',[['Item','Item_ID'],['Date','Effective_Date'],['Price change %','Observed_Price_Change_Percent'],['Old demand','Before_Quantity'],['New demand','After_Quantity'],['Demand change %','Demand_Change_Percent'],['Contribution change %','Contribution_Change_Percent'],['Sensitivity','Sensitivity']],'observations'),
      promotions: () => showSimple('/api/analytics/promotions','Promotion Economics',[['Campaign','promotion_name'],['Units','quantity'],['Net revenue','revenue',money],['Contribution','contribution',money],['Orders','orders'],['AOV','aov',money],['Repeat customers','repeat_customers'],['Wastage cost','wastage_cost',money],['Trap','promotion_trap',x => x === null ? 'Insufficient window' : x ? 'Yes' : 'No']],'campaigns'),
      anomalies: () => showSimple('/api/analytics/anomalies','Sales Anomalies',[['Date','Date'],['Location','Location_ID'],['Quantity','quantity'],['Z score','z_score']],'sales'),
      'rating-anomalies': () => showSimple('/api/analytics/anomalies','Rating Anomalies',[['Item','Item_ID'],['Day','Rating_Day'],['Ratings','count'],['Average stars','average_stars'],['5-star rate','five_star_rate'],['Count Z','count_z_score']],'ratings'),
      channels: () => showSimple('/api/analytics/channels','Ordering Channels',[['Channel','Channel'],['Orders','orders'],['Customers','customers'],['Net revenue','revenue',money],['Contribution','contribution',money],['AOV','aov',money]],'channels'),
      locations: () => showSimple('/api/analytics/locations','Location Comparison',[['Location','Location_ID'],['Revenue rank','revenue_rank'],['Orders','orders'],['Net revenue','revenue',money],['Contribution','contribution',money],['AOV','aov',money],['Wastage','wastage_cost',money]],'locations'),
      churn: () => showSimple('/api/analytics/churn','At-Risk Customers',[['Customer','Customer_ID'],['Segment','Segment'],['Recency days','Recency_Days'],['Recent orders','recent_orders'],['Prior orders','previous_orders'],['Net monetary','Monetary',money]],'at_risk'),
      recommendations: () => showSimple('/api/analytics/recommendations','Recommendations',[['Item','entity_id'],['Type','type'],['Priority','priority'],['Action','action'],['Reason','reason']],'recommendations')};
    if (!handlers[page]) return;
    view.innerHTML = '<p>Loading live analytics...</p>';
    try { await handlers[page](); } catch(error) { view.innerHTML = title('Unable to load data') + `<div class="alert alert-danger">${esc(error.message)}</div>`; }
  });
})();
