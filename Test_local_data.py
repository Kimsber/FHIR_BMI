import requests
import json

server_url = "https://twcore.hapi.fhir.tw/fhir/"
setting = "?_format=json&_pretty=true"
resource = "Observation"  # 可填入想要搜尋的參數，若為空則搜尋整個Condition
# parameters = "?" # 查詢操作參數可簡化資料處理
access_token = (requests.get(str(server_url + resource + setting), verify=False)).text
RequestResult = json.loads(access_token)

print(RequestResult)
len(RequestResult)
RequestResult.keys()

# 取得資料本體
dataset = [i for i in RequestResult.get("entry")]
len(dataset)

# 判斷是否含 1.) BMI 2.) 身高和體重
# 從IG找對應的Code，某單一名詞可能對應到多個Code(分類和分支)
code_parent = [
    "85353-1"
]  # LONIC: Vital signs, weight, height, head circumference, oxygen saturation and BMI panel
code_child = [
    "39156-5",
    "8302-2",
    "29463-7",
]  # LONIC: Body mass index (BMI) [Ratio], Body height, Body weight
dataset_target = []
for i in dataset:
    # 確認最外層code 是否包含 code_parent 或 code_child
    if i.get("resource").get("code").get("coding")[0].get("code") in (
        code_parent or code_child
    ):
        # 如果是以code_parent 納入，需要向下確認component是否含有需要的元素(code_child)
        # 有些檢驗由多個項目組成，這些組成之檢驗被表達為具有相同屬性(code_parent)的獨立的代碼值對(code-value pair)
        for j in i.get("resource").get("component"):
            if j.get("code").get("coding")[0].get("code") in code_child:
                dataset_target.append(i)

len(dataset_target)
for i in dataset_target:
    print(i)

# 確認資料: 無BMI者須計算
for i in dataset_target:
    # 假設無component
    if i.get("resource").get("code").get("coding")[0].get("code") in code_child:
        if i.get("resource").get("code").get("coding")[0].get("code") == code_child[0]:
            BMI = (
                i.get("resource").get("code").get("coding")[0].get("code")
                == code_child[0]
            )
        else:
            if (
                i.get("resource").get("code").get("coding")[0].get("code")
                == code_child[1]
            ):
                Height = i.get("resource").get("valueQuantity")  # 增加條件
            if (
                i.get("resource").get("code").get("coding")[0].get("code")
                == code_child[2]
            ):
                Weight = i.get("resource").get("valueQuantity")  #

    # 取component
    else:
        Height = i.get("resource").get("component").get("coding")[0].get("code")
        Weight = i.get("resource").get("code").get("coding")[0].get("code")

    BMI = Weight / (Height / 100) ^ 2


with open(
    "C:/Users/USER/Documents/FHIR-EX/AllergyIntolerance-all-nut-example.json",
    "r",
    encoding="utf-8",
) as f:
    data = json.load(f)
    datas = json.dumps(data, indent=4)
