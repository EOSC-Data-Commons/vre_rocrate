from vre_rocrate import MinimalVRERequest, MinimalFileInput, RocrateBuilder


parameter_file=MinimalFileInput(name="parameter_file", url="https://www.creatis.insa-lyon.fr/~abonnet/quest_param_117T_A.txt", encoding_format="txt")
data_file=MinimalFileInput(name="data_file", url="https://www.creatis.insa-lyon.fr/~abonnet/Rec003_Vox1.mrui", encoding_format="application/octet-stream")
zipped_folder=MinimalFileInput(name="zipped_folder", url="https://www.creatis.insa-lyon.fr/~abonnet/basis_11_7.zip", encoding_format="application/zip")

minimal = MinimalVRERequest(vre_type="vip", workflow="https://vip.creatis.insa-lyon.fr/rest/pipelines/CQUEST/0.6",
                            files=[parameter_file, data_file, zipped_folder])
    
RocrateBuilder.build_from_minimal(minimal)