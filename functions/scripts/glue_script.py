import sys
from awsglue.dynamicframe import DynamicFrame
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
data_sheets = ['volts', 'amps', 'watts', 'power_factor', 'watt_hours']
args = getResolvedOptions(sys.argv, ['JOB_NAME',
                                     'database',
                                     'ingest_table',
                                     'target_bucket',
                                     'TempDir'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)
DataSource0 = glueContext.create_dynamic_frame.from_catalog(database=args['database'],
                                                            table_name=args['ingest_table'],
                                                            transformation_ctx="DataSource0")
relationalize_json = DataSource0.relationalize(root_table_name="root",
                                               staging_path=args['TempDir'])

root_df = relationalize_json.select('root')
root_vals_df = relationalize_json.select('root_values')
root_df = root_df.toDF()
root_vals_df = root_vals_df.toDF()
joined_data = root_df.join(root_vals_df, (root_df.values == root_vals_df.id),
                           how="left_outer")
joined_data.createOrReplaceTempView("join_table")
columns = []
for i, d in enumerate(data_sheets):
    sql = """SELECT `values.val.timestamp` as timestamp_{},
    case when `property_type` = 'INTEGER' then `values.val.value.int` else `values.val.value.double` end as {}
    FROM join_table
    where `name` = '{}'""".format(i, d, d)
    current_table = spark.sql(sql)
    columns.append(current_table)


final_table = columns[0].join(columns[1], (columns[0].timestamp_0 == columns[1].timestamp_1), how="left_outer")
final_table = final_table.join(columns[2], (final_table.timestamp_0 == columns[2].timestamp_2), how="left_outer")
final_table = final_table.join(columns[3], (final_table.timestamp_0 == columns[3].timestamp_3), how="left_outer")
final_table = final_table.join(columns[4], (final_table.timestamp_0 == columns[4].timestamp_4), how="left_outer")
final_table.createOrReplaceTempView("final_table")
sql = """select `timestamp_0` as timestamp, `volts`, `amps`, `watts`, `power_factor`, `watt_hours` 
from final_table 
order by `timestamp_0` desc"""

final_table = spark.sql(sql)
final_frame = DynamicFrame.fromDF(final_table, glueContext, "final_table")
final_frame_repartitioned = final_frame.repartition(1)
DatasinkFinal = glueContext.write_dynamic_frame.from_options(frame=final_frame_repartitioned,
                                                             format_options={'withHeader': True,
                                                                             'writeHeader': True},
                                                             connection_type="s3",
                                                             format="csv",
                                                             connection_options={'path': args['target_bucket'],
                                                                                 'partitionKeys': []},
                                                             transformation_ctx="DataSinkFinal")
job.commit()