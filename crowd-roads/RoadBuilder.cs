using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using EasyRoads3Dv3;


public class RoadBuilder : MonoBehaviour
{
    public Vector3 screenPosition, worldPosition;
    public Vector3 startCoord;
    public Vector3 endCoord;
    public ERRoadNetwork roadNetwork;
    public ERRoadType roadType;
    public Plane plane;

    private bool dragging = false;
    private ERRoad currentRoad;
    private Collider coll;

    void Start() {
        Debug.Log("Please read the comments at the top of the runtime script (/Assets/EasyRoads3D/Scripts/runtimeScript) before using the runtime API!");
        
        roadNetwork = new ERRoadNetwork();

        roadType = new ERRoadType();
		roadType.roadWidth = 6;
		roadType.roadMaterial = Resources.Load("Materials/roads/road material") as Material;
        roadType.layer = 1;
        roadType.tag = "Untagged";

        coll = GetComponent<Collider>();
    }

    void Update() {
        Vector3? coord = GetMouseWorldCoord();
        if (coord != null) {
            endCoord = (Vector3) coord;
        }
        if (dragging && currentRoad != null) {
            if (coord != null) {
                UpdateRoadEndCoord(currentRoad, (Vector3) coord);
            }
        }
    }

    void OnMouseDown() {
        dragging = true;
        Vector3? startCoord = GetMouseWorldCoord();
        if (startCoord != null) {
            currentRoad = CreateRoad("Road", roadType, (Vector3) startCoord);
            currentRoad.SetWidth(5);
        }
    }
    
    void OnMouseUp() {
        dragging = false;
        HashSet<ERRoad> connectedRoads = GetConnectedRoads(currentRoad);
        foreach (ERRoad connectedRoad in connectedRoads) {
            roadNetwork.ConnectRoads(currentRoad, connectedRoad);
        }
        // Debug.Log(connectedRoads.Count);
        currentRoad = null;
    }

    private Vector3? GetMouseWorldCoord() {
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        if (coll.Raycast(ray, out RaycastHit hit, 1000.0f)) {
            Vector3 point = ray.GetPoint(hit.distance);
            point.y = 0.05f;
            return point;
        }

        return null;
    }

    private Vector3 SnapToGrid(Vector3 pos) {
        return new Vector3(Mathf.Round(pos.x),
                             pos.y,
                             Mathf.Round(pos.z));
    }

    private ERRoad CreateRoad(string name, ERRoadType roadType, Vector3 startCoord) {
        ERRoad road = roadNetwork.CreateRoad(name, roadType);
        Vector3 coord = SnapToGrid(startCoord);
        road.AddMarker(coord);
        road.AddMarker(coord);
        return road;
    }

    private void UpdateRoadEndCoord(ERRoad road, Vector3 endCoord) {
        Vector3 coord = SnapToGrid(endCoord);
        road.DeleteMarker(1);
        road.InsertMarker(coord);
    }

    private HashSet<ERRoad> GetConnectedRoads(ERRoad currentRoad) {
        Vector3 startCoord = currentRoad.GetMarkerPosition(0);
        Vector3 endCoord = currentRoad.GetMarkerPosition(1);
        HashSet<ERRoad> roads = new HashSet<ERRoad>();
        foreach (ERRoad road in roadNetwork.GetRoadObjects()) {
            if (road == currentRoad) continue;
            Vector3[] markerPositions = road.GetMarkerPositions();
            foreach (Vector3 pos in markerPositions) {
                if (pos == startCoord || pos == endCoord) {
                    roads.Add(road);
                    break;
                }
            }
        }
        return roads;
    }
}
