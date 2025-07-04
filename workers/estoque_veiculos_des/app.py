import jaydebeapi
import json
import requests
from dotenv import load_dotenv
import os
from time import sleep
load_dotenv()

def conn_oracle():
    driver_class = "oracle.jdbc.OracleDriver"
    jdbc_url = f"jdbc:oracle:thin:@{os.getenv('ORACLE_HOST')}:{os.getenv('ORACLE_PORT')}:{os.getenv('ORACLE_DATABASE')}"
    driver_args = [
        "jdbc/oracle-jdbc-11.jar",
        "jdbc/postgresql-42.7.5.jar"
    ]
    conn = jaydebeapi.connect(driver_class, jdbc_url, [os.getenv('ORACLE_USERNAME'), os.getenv('ORACLE_PASSWORD')], driver_args)
    conn.jconn.setAutoCommit(False)
    cur = conn.cursor()
    return conn, cur


while True:

    conn, cur = conn_oracle()

    query = f"""
        SELECT 
        CASE
            WHEN v.cod_empresa = 111 THEN 11
            WHEN v.cod_empresa = 11 THEN 11
            WHEN v.cod_empresa = 33 THEN 33
            ELSE
            11
        END idClient, 
        CASE 
            WHEN v.NOVO_USADO = 'N' THEN 'NOVO'
            ELSE
            'USADO'
        END vehicleStatus,
        v.ANO_MODELO yearFab,
        v.ANO_MODELO yearMod,
        v.CHASSI_COMPLETO chassi,
        c.combustivel fuel,
        ce.DESCRICAO color,
        pm.DESCRICAO_MODELO model,
        ROUND(SYSDATE - v.data_entrada) AS daysInStock,
        NVL(v.KM_USADO, 0) KM,
        p.DESCRICAO storeYard,
        v.PLACA_USADO plate,
        v.RENAVAM renavam,
        CASE
                WHEN v.COD_PROPOSTA = 0 THEN NULL
                ELSE v.COD_PROPOSTA
            END AS proposalNumber,
            'NAO DEFINIDO' vehicleProposalStatus,
        v.PRECO_TABELA tableSalesValue,
        eu.NOME_COMPLETO salesPerson,
        eu.NOME_COMPLETO reserveEmployee,
        eu.NOME_COMPLETO seller,
        CASE 
            WHEN v.NOVO_USADO = 'U' THEN v.TOTAL_NOTA_FABRICA 
            ELSE
            null
        END assessedValue,
        m.DESCRICAO_MARCA brand,
        CASE
            WHEN v.cod_empresa = '111' THEN '02521849000136'
            WHEN v.cod_empresa = '11' THEN '02521849000136'
            WHEN v.cod_empresa = '33' THEN '08765777000159'
            ELSE
            '02521849000136'
        END cnpjClient
        FROM veiculos v
        LEFT JOIN produtos_modelos pm ON 1=1
                AND pm.COD_PRODUTO = v.COD_PRODUTO 
                AND pm.COD_MODELO = v.COD_MODELO 
        LEFT JOIN cores_externas ce ON 1=1
            AND ce.cor_externa = v.COR_EXTERNA
        LEFT JOIN combustivel c ON 1=1
            AND c.cod_combustivel = v.cod_combustivel
        LEFT JOIN patio p ON 1=1
            AND p.COD_PATIO = v.COD_PATIO 
        LEFT JOIN VEICULOS_PROPOSTAS vp ON 1=1
            AND v.COD_PROPOSTA = vp.COD_PROPOSTA 
            AND v.COD_EMPRESA = vp.COD_EMPRESA 
        LEFT JOIN EMPRESAS_USUARIOS eu ON 1=1
            AND eu.nome = vp.VENDEDOR 
        LEFT JOIN produtos p ON 1=1
            AND p.cod_produto = pm.COD_PRODUTO 
        LEFT JOIN marcas m ON 1=1
            AND m.COD_MARCA = p.cod_marca
        WHERE 1=1
            AND v.status = 'E'
            AND v.NOVO_USADO IN ('N','U')
            AND v.cod_empresa in (11,33,111)
            --and v.chassi_completo = '93HGK5860GZ236646'
    """
    cur.execute(query)
    r = cur.fetchall()
    veiculos = []

    for i in r:

        veiculo = {
            "refId" : None,
            "cnpjClient" : None,
            "shortDescription" : None,
            "vehicleStatus" : None,
            "vehicleHeight" : None,
            "yearFab" : None,
            "yearMod" : None,
            "icmsCalcBasis" : None,
            "cancellationDt" : None,
            "vehicleNumber" : None,
            "chassi" : None,
            "engineDisplacement" : None,
            "cylinders" : None,
            "cofinsShippingCost" : None,
            "cofinsCostRecovered" : None,
            "cofinsCost" : None,
            "fuel" : None,
            "vehicleLength" : None,
            "chassiCondition" : None,
            "vehicleCondition" : None,
            "color" : None,
            "crlv" : None,
            "crv" : None,
            "model" : None,
            "arrivalDt" : None,
            "saleDt" : None,
            "reservationDt" : None,
            "personInPossessionVehicle" : None,
            "accessoriesExpenseValue" : None,
            "departureDays" : None,
            "daysInStock" : None,
            "daysInReserve" : None,
            "vehicleSteeringWheel" : None,
            "wheelbase" : None,
            "inboundFiscalDoc" : None,
            "invoiceDt" : None,
            "vehicleType" : None,
            "frontBrake" : None,
            "rearBrake" : None,
            "isFleetOwner" : None,
            "hp" : None,
            "icmsDownPaymentValue" : None,
            "icmsValueRecovered" : None,
            "icmsShippingCost" : None,
            "notes" : None,
            "valueIpi" : None,
            "km" : None,
            "vehicleWidth" : None,
            "factoryBatch" : None,
            "vehicleGears" : None,
            "maxTractionCapacity" : None,
            "cancellationReason" : None,
            "engineNumber" : None,
            "proposalNumber" : None,
            "serialNumber" : None,
            "reserveObservation" : None,
            "origin" : None,
            "vehicleOriginSale" : None,
            "maxNumberPassengers" : None,
            "storeYard" : None,
            "vehicleGrossWeight" : None,
            "vehicleNetWeight" : None,
            "person" : None,
            "pisShippingCost" : None,
            "pisCostRecovered" : None,
            "pisValue" : None,
            "plate" : None,
            "expectedArrivalDt" : None,
            "renavam" : None,
            "reserveName" : None,
            "fuelTank" : None,
            "supplierDepartureDt" : None,
            "stockSituation" : None,
            "vehicleProposalStatus" : None,
            "reserveStatus" : None,
            "fiscalDocType" : None,
            "salesTypeVehicle" : None,
            "vehicleTransmission" : None,
            "stateTaxation" : None,
            "acronymUnitMeasurement" : None,
            "validity" : None,
            "colorSaleValue" : None,
            "shippingCost" : None,
            "optionalValues" : None,
            "insuranceValue" : None,
            "suggestedAssociationValue" : None,
            "factorySuggestedValue" : None,
            "tableSalesValue" : None,
            "totalDownPaymentValue" : None,
            "accountingCostValue" : None,
            "totalSaleValue" : None,
            "salesPerson" : None,
            "hasDamage" : None,
            "reserveEmployee" : None,
            "evaluationForm" : None,
            "evaluator" : None,
            "seller" : None,
            "assessedValue" : None,
            "checklistExpenses" : None,
            "brand" : None,
            "bodyRepair" : None,
            "modelGroup" : None,
            "modelType" : None,
            "docValue" : None,
            "maintenanceValue" : None,
            "orderNumber" : None,
            "productionWeek" : None,
            "bodyRepairValue" : None,
            "orderMonthYear" : None,
            "vehicleStatusReport" : None,
            "fleetOwner" : None
        }
        
        veiculo["refId"] = i[4]
        veiculo["vehicleStatus"] = i[1]
        veiculo["yearFab"] = i[2]
        veiculo["yearMod"] = i[3]
        veiculo["chassi"] = i[4]
        veiculo["fuel"] = i[5]
        veiculo["color"] = i[6]
        veiculo["model"] = i[7]
        veiculo["daysInStock"] = i[8]
        veiculo["km"] = i[9]
        veiculo["storeYard"] = i[10]
        veiculo["plate"] = i[11]
        veiculo["renavam"] = i[12]
        veiculo["proposalNumber"] = i[13]
        veiculo["vehicleProposalStatus"] = i[14]
        veiculo["tableSalesValue"] = i[15]
        veiculo["salesPerson"] = i[16]
        veiculo["reserveEmployee"] = i[17]
        veiculo["seller"] = i[18]
        veiculo["assessedValue"] = i[19]
        veiculo["brand"] = i[20]
        veiculo["yearFab"] = "20" + str(veiculo["yearFab"].split("/")[1])
        veiculo["yearMod"] = "20" + str(veiculo["yearMod"].split("/")[0])
        veiculo["cnpjClient"] = i[21]


        veiculos.append(veiculo)

    # Fecha a conexão
    conn.close()

    url = "https://caiuas-miner-api.dealerequity.com.br/api/auth/login"

    payload = json.dumps({
    "username": os.getenv('DES_USER'),
    "password": os.getenv('DES_PASSWORD')
    })
    headers = {
    'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception("Erro ao autenticar na API")
    token = response.json()["token"]

    with open("veiculos2.json", "w") as f:
        json.dump(veiculos, f)

    url = "https://caiuas-miner-api.dealerequity.com.br/api/push/vehicle-stock"
    payload = json.dumps(veiculos)
    # print(payload)
    # exit()
    headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code != 201:
        raise Exception("Erro ao enviar veículos para a API")
    
    print(f"Veículos enviados: {len(veiculos)}")
    sleep(600)  