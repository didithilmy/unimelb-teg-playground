using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using EasyRoads3Dv3;

[CustomEditor(typeof(RoadBuilder))]
public class RoadBuilderEditor : Editor
{

    private GameObject trafficLightGameObject = null, footpathGameObject = null;
    private int fromLane = 0, toLane = 0;
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();
        RoadBuilder roadBuilder = (RoadBuilder)target;
        trafficLightGameObject = (GameObject)EditorGUILayout.ObjectField("Traffic light", trafficLightGameObject, typeof(GameObject), true);
        fromLane = EditorGUILayout.IntField("From lane", fromLane);
        toLane = EditorGUILayout.IntField("To lane", toLane);


        if (GUILayout.Button("Connect lane to traffic light"))
        {
            TSMainManager tsMainManager = roadBuilder.itsManager.GetComponent<TSMainManager>();
            TSTrafficLight trafficLight = trafficLightGameObject.GetComponent<TSTrafficLight>();
            TSLaneInfo fromLaneInfo = tsMainManager.lanes[fromLane];
            TSLaneInfo toLaneInfo = tsMainManager.lanes[toLane];
            roadBuilder.ConnectLaneToTrafficLight(trafficLight, fromLaneInfo, toLaneInfo);
        }

        if (GUILayout.Button("Disonnect lane from traffic light"))
        {
            TSMainManager tsMainManager = roadBuilder.itsManager.GetComponent<TSMainManager>();
            TSTrafficLight trafficLight = trafficLightGameObject.GetComponent<TSTrafficLight>();
            TSLaneInfo fromLaneInfo = tsMainManager.lanes[fromLane];
            TSLaneInfo toLaneInfo = tsMainManager.lanes[toLane];
            roadBuilder.DisconnectLaneFromTrafficLight(trafficLight, fromLaneInfo, toLaneInfo);
        }
    }
}
