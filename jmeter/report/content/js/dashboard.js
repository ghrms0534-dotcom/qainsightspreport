/*
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/
var showControllersOnly = false;
var seriesFilter = "";
var filtersOnlySampleSeries = true;

/*
 * Add header in statistics table to group metrics by category
 * format
 *
 */
function summaryTableHeader(header) {
    var newRow = header.insertRow(-1);
    newRow.className = "tablesorter-no-sort";
    var cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Requests";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 3;
    cell.innerHTML = "Executions";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 7;
    cell.innerHTML = "Response Times (ms)";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Throughput";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 2;
    cell.innerHTML = "Network (KB/sec)";
    newRow.appendChild(cell);
}

/*
 * Populates the table identified by id parameter with the specified data and
 * format
 *
 */
function createTable(table, info, formatter, defaultSorts, seriesIndex, headerCreator) {
    var tableRef = table[0];

    // Create header and populate it with data.titles array
    var header = tableRef.createTHead();

    // Call callback is available
    if(headerCreator) {
        headerCreator(header);
    }

    var newRow = header.insertRow(-1);
    for (var index = 0; index < info.titles.length; index++) {
        var cell = document.createElement('th');
        cell.innerHTML = info.titles[index];
        newRow.appendChild(cell);
    }

    var tBody;

    // Create overall body if defined
    if(info.overall){
        tBody = document.createElement('tbody');
        tBody.className = "tablesorter-no-sort";
        tableRef.appendChild(tBody);
        var newRow = tBody.insertRow(-1);
        var data = info.overall.data;
        for(var index=0;index < data.length; index++){
            var cell = newRow.insertCell(-1);
            cell.innerHTML = formatter ? formatter(index, data[index]): data[index];
        }
    }

    // Create regular body
    tBody = document.createElement('tbody');
    tableRef.appendChild(tBody);

    var regexp;
    if(seriesFilter) {
        regexp = new RegExp(seriesFilter, 'i');
    }
    // Populate body with data.items array
    for(var index=0; index < info.items.length; index++){
        var item = info.items[index];
        if((!regexp || filtersOnlySampleSeries && !info.supportsControllersDiscrimination || regexp.test(item.data[seriesIndex]))
                &&
                (!showControllersOnly || !info.supportsControllersDiscrimination || item.isController)){
            if(item.data.length > 0) {
                var newRow = tBody.insertRow(-1);
                for(var col=0; col < item.data.length; col++){
                    var cell = newRow.insertCell(-1);
                    cell.innerHTML = formatter ? formatter(col, item.data[col]) : item.data[col];
                }
            }
        }
    }

    // Add support of columns sort
    table.tablesorter({sortList : defaultSorts});
}

$(document).ready(function() {

    // Customize table sorter default options
    $.extend( $.tablesorter.defaults, {
        theme: 'blue',
        cssInfoBlock: "tablesorter-no-sort",
        widthFixed: true,
        widgets: ['zebra']
    });

    var data = {"OkPercent": 100.0, "KoPercent": 0.0};
    var dataset = [
        {
            "label" : "FAIL",
            "data" : data.KoPercent,
            "color" : "#FF6347"
        },
        {
            "label" : "PASS",
            "data" : data.OkPercent,
            "color" : "#9ACD32"
        }];
    $.plot($("#flot-requests-summary"), dataset, {
        series : {
            pie : {
                show : true,
                radius : 1,
                label : {
                    show : true,
                    radius : 3 / 4,
                    formatter : function(label, series) {
                        return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">'
                            + label
                            + '<br/>'
                            + Math.round10(series.percent, -2)
                            + '%</div>';
                    },
                    background : {
                        opacity : 0.5,
                        color : '#000'
                    }
                }
            }
        },
        legend : {
            show : true
        }
    });

    // Creates APDEX table
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.9981818181818182, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [1.0, 500, 1500, "GET Combo Data (초기 코드 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Defect Search (결함관리 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Deliverable Consistency Grid2 (산출물정합성체크 조회2)"], "isController": false}, {"data": [1.0, 500, 1500, "Login Thread Group (로그인 테스트)"], "isController": true}, {"data": [1.0, 500, 1500, "GET DevStatus Search (개발현황 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET File Management Search (파일관리 조회)"], "isController": false}, {"data": [0.96, 500, 1500, "Browse Thread Group (조회 테스트)"], "isController": true}, {"data": [1.0, 500, 1500, "GET Meeting Room Reservation Search (회의실 예약 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Main Page (ProjectEyes현황 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET IntegrationTestProgress Search (통합테스트진척현황)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Weekly Report Search (주간보고 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Deployment Request Search (배포요청 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Deliverable Consistency Grid1 (산출물정합성체크 조회1)"], "isController": false}, {"data": [1.0, 500, 1500, "GET IntegrationTest Search (통합테스트 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Meeting Minutes Search (회의록 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET ActionItemIssue Search (이슈관리 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Project Dev Board Search (프로젝트개발게시판 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET Login Page (로그인 페이지)"], "isController": false}, {"data": [1.0, 500, 1500, "GET DevProgress Search (개발진척현황 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET PMS Request Search (PMS신청관리 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "GET AsIsToBe Mapping Search (ASIS-TOBE매핑관리 조회)"], "isController": false}, {"data": [1.0, 500, 1500, "POST Signin (로그인)"], "isController": false}]}, function(index, item){
        switch(index){
            case 0:
                item = item.toFixed(3);
                break;
            case 1:
            case 2:
                item = formatDuration(item);
                break;
        }
        return item;
    }, [[0, 0]], 3);

    // Create statistics table
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 2000, 0, 0.0, 23.074999999999985, 2, 380, 14.0, 42.90000000000009, 85.89999999999964, 157.96000000000004, 14.177057268222834, 63.43817784055064, 4.536242982356652], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["GET Combo Data (초기 코드 조회)", 100, 0, 0.0, 14.020000000000001, 3, 149, 7.0, 23.400000000000034, 57.0, 148.93999999999997, 1.001763103061388, 2.640389272619811, 0.20250484602901106], "isController": false}, {"data": ["GET Defect Search (결함관리 조회)", 100, 0, 0.0, 18.139999999999997, 4, 184, 10.0, 27.900000000000006, 78.59999999999968, 183.68999999999983, 1.0093363613424173, 0.4701693792581378, 0.1882648877113298], "isController": false}, {"data": ["GET Deliverable Consistency Grid2 (산출물정합성체크 조회2)", 100, 0, 0.0, 22.669999999999998, 8, 186, 18.5, 32.60000000000002, 43.89999999999998, 185.82999999999993, 0.9915224827722968, 7.599090278122056, 0.30888249219176045], "isController": false}, {"data": ["Login Thread Group (로그인 테스트)", 100, 0, 0.0, 136.32000000000005, 78, 434, 124.5, 188.00000000000006, 276.84999999999997, 433.5999999999998, 1.0093465490441489, 6.810132136080102, 0.6811117826069403], "isController": true}, {"data": ["GET DevStatus Search (개발현황 조회)", 100, 0, 0.0, 27.43, 11, 201, 23.5, 37.0, 51.64999999999992, 200.30999999999966, 1.0247266541650015, 30.363531387377417, 0.4853441672558845], "isController": false}, {"data": ["GET File Management Search (파일관리 조회)", 100, 0, 0.0, 14.540000000000004, 5, 84, 12.0, 25.900000000000006, 29.94999999999999, 83.78999999999989, 0.9723086496577473, 5.330606210135345, 0.20604587595286247], "isController": false}, {"data": ["Browse Thread Group (조회 테스트)", 100, 0, 0.0, 325.17999999999995, 196, 723, 288.0, 463.20000000000005, 638.6999999999995, 722.81, 1.009234495635061, 83.51119777211485, 5.777473255285866], "isController": true}, {"data": ["GET Meeting Room Reservation Search (회의실 예약 조회)", 100, 0, 0.0, 15.709999999999997, 6, 206, 11.0, 23.700000000000017, 42.399999999999864, 204.65999999999931, 0.9785310292189364, 0.45581962982171165, 0.2656558848856097], "isController": false}, {"data": ["GET Main Page (ProjectEyes현황 조회)", 100, 0, 0.0, 13.790000000000003, 2, 158, 8.0, 25.700000000000017, 58.399999999999864, 157.3999999999997, 1.0233005536055995, 2.6971564396303838, 0.12791256920069993], "isController": false}, {"data": ["GET IntegrationTestProgress Search (통합테스트진척현황)", 100, 0, 0.0, 20.029999999999998, 5, 111, 15.0, 40.70000000000002, 57.69999999999993, 110.81999999999991, 1.0132122882386319, 1.5356498743616762, 0.357196910209127], "isController": false}, {"data": ["GET Weekly Report Search (주간보고 조회)", 100, 0, 0.0, 22.31, 10, 83, 21.0, 31.0, 36.89999999999998, 82.64999999999982, 0.9849693674526723, 6.010814040245848, 0.4366954031479621], "isController": false}, {"data": ["GET Deployment Request Search (배포요청 조회)", 100, 0, 0.0, 15.279999999999996, 6, 71, 13.0, 23.600000000000023, 32.0, 70.99, 0.9650832866876411, 2.3684124018027757, 0.3242076666216295], "isController": false}, {"data": ["GET Deliverable Consistency Grid1 (산출물정합성체크 조회1)", 100, 0, 0.0, 14.909999999999995, 5, 178, 10.5, 22.80000000000001, 44.94999999999999, 176.7899999999994, 1.0047322890815742, 0.46802470887881925, 0.3129976564619357], "isController": false}, {"data": ["GET IntegrationTest Search (통합테스트 조회)", 100, 0, 0.0, 24.540000000000006, 7, 372, 17.0, 34.60000000000002, 71.34999999999985, 369.76999999999884, 1.0185788787483703, 13.574751912381844, 0.45657002475146674], "isController": false}, {"data": ["GET Meeting Minutes Search (회의록 조회)", 100, 0, 0.0, 19.199999999999996, 6, 380, 12.0, 30.50000000000003, 39.94999999999999, 377.7399999999989, 0.9802672208444022, 0.9438901169458794, 0.25751160391322675], "isController": false}, {"data": ["GET ActionItemIssue Search (이슈관리 조회)", 100, 0, 0.0, 20.66, 5, 251, 13.0, 33.900000000000006, 70.44999999999987, 249.74999999999937, 1.006066581486363, 4.205043914806281, 0.5118756728070264], "isController": false}, {"data": ["GET Project Dev Board Search (프로젝트개발게시판 조회)", 100, 0, 0.0, 14.0, 5, 101, 12.0, 19.0, 30.849999999999966, 100.47999999999973, 0.9702614854703342, 1.1133371537379324, 0.3799559137437539], "isController": false}, {"data": ["GET Login Page (로그인 페이지)", 100, 0, 0.0, 22.77, 7, 321, 13.0, 36.0, 60.849999999999966, 319.9999999999995, 1.0074450186881052, 2.6553653373429644, 0.1879121079779571], "isController": false}, {"data": ["GET DevProgress Search (개발진척현황 조회)", 100, 0, 0.0, 19.47, 7, 227, 15.5, 29.80000000000001, 40.74999999999994, 225.4299999999992, 1.0143119414944872, 3.063737143596142, 0.417016921258964], "isController": false}, {"data": ["GET PMS Request Search (PMS신청관리 조회)", 100, 0, 0.0, 25.370000000000005, 8, 217, 17.0, 33.900000000000006, 82.6499999999997, 216.6099999999998, 1.0027073097362882, 0.883244134162238, 0.37503603479394365], "isController": false}, {"data": ["GET AsIsToBe Mapping Search (ASIS-TOBE매핑관리 조회)", 100, 0, 0.0, 17.13, 4, 136, 13.0, 26.900000000000006, 39.799999999999955, 135.45999999999972, 1.0036734448079974, 2.354319935965634, 0.3058067527149367], "isController": false}, {"data": ["POST Signin (로그인)", 100, 0, 0.0, 99.52999999999999, 64, 255, 105.0, 116.0, 137.95, 254.50999999999976, 1.0105705681427735, 1.491183719202862, 0.28915739889241465], "isController": false}]}, function(index, item){
        switch(index){
            // Errors pct
            case 3:
                item = item.toFixed(2) + '%';
                break;
            // Mean
            case 4:
            // Mean
            case 7:
            // Median
            case 8:
            // Percentile 1
            case 9:
            // Percentile 2
            case 10:
            // Percentile 3
            case 11:
            // Throughput
            case 12:
            // Kbytes/s
            case 13:
            // Sent Kbytes/s
                item = item.toFixed(2);
                break;
        }
        return item;
    }, [[0, 0]], 0, summaryTableHeader);

    // Create error table
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": []}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 2000, 0, "", "", "", "", "", "", "", "", "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
