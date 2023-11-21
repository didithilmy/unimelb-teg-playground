using System;
using System.Collections.Generic;
using System.Linq;
using ITS.AI;
using ITS.Utils;
using UnityEngine;
using UnityEngine.Assertions;
using UnityEngine.Serialization;
using Random = UnityEngine.Random;

/// <summary>
/// TS lane info.  This class is responsible for holding all the lane information.
/// </summary>
[System.Serializable]
public class TSLaneInfo : TSBaseInfo
{
    public TSLaneInfo() {}
    public TSLaneInfo(Vector3 startPoint, Vector3 endPoint, float resolution, VehicleType defaultVehicleType):base(startPoint,endPoint,resolution, defaultVehicleType)
    {
        connectors = new TSLaneConnector[0];
        points = new TSPoints[0];
        var pts = new[]{conectorA, conectorA, middlePoints[0], conectorB, conectorB};
        TSUtils.CreatePoints(resolution, pts, ref points, ref totalDistance);
    }

    public void CreateWaypoints(float resolution)
    {
        CreateWaypoints<TSPoints>(resolution, ref points);
    }
    
    [NonSerialized] protected new TSLaneInfo[] _lanes;

    public float laneWidth = 2f;
    public TSLaneConnector[] connectors;
    public TSPoints[] points;
    [NonSerialized] public TSLaneConnector[] connectorsReverse = new TSLaneConnector[0];
    public float trafficDensity = 1f;
    [FormerlySerializedAs("maxTotalOcupation")] public float maxTotalOccupation = 75f;

    public bool HasFreeOccupation => TotalOccupation < maxTotalOccupation;
    public bool HasFreeDensity => TotalOccupation < trafficDensity * 100f;
    public float TotalOccupation { get; private set; }
    public enum VehicleType
    {
        Taxi,
        Bus,
        Light,
        Medium,
        Heavy,
        Train,
        Heavy_Machinery,
        Pedestrians,
        Racer,
        Bicycle
    }

    public override TSPoints[] Points => points;
    public Vector3 EndDirection => points[points.Length - 3].point - conectorB;
    public Vector3 StartDirection => conectorA - points[2].point;

    public override TSBaseInfo GetNext(VehicleType _vehicleType)
    {
        var baseInfo = GetLaneFromConnectors(_vehicleType, connectors);
        return baseInfo;
    }

    public override TSBaseInfo GetPrevious(VehicleType _vehicleType)
    {
        return GetLaneFromConnectors(_vehicleType, connectorsReverse);
    }

    /*public override TSBaseInfo GetNext(VehicleType _vehicleType, out bool reversed)
    {
        reversed = false;
        return GetNext(_vehicleType);
    }

    public override TSBaseInfo GetPrevious(VehicleType _vehicleType, out bool reversed)
    {
        var connector = GetLaneFromConnectors(_vehicleType, connectorsReverse);
        reversed = false;
        return connector;
    }*/

    private TSBaseInfo GetLaneFromConnectors(VehicleType _vehicleType, TSLaneConnector[] connectorsList)
    {
        if (connectorsList.Length == 0)
        {
            return null;
        }

        var maxInt = float.MaxValue;
        var index = ITS.Utils.Random.Range(0, connectorsList.Length);

        for (int i = 0; i < connectorsList.Length; i++)
        {
            float randomWeight;
            if (connectorsList[i].NextLane.HasVehicleType(_vehicleType) && connectorsList[i].HasVehicleType(_vehicleType))
            {
                randomWeight = connectorsList[i].NextLane.TotalOccupation * ITS.Utils.Random.Range(0, connectorsList.Length * ITS.Utils.Random.Range(0f, 1f));
            }
            else
            {
                randomWeight = float.MaxValue - ITS.Utils.Random.Range(0, connectorsList.Length);
            }

            if (randomWeight < maxInt && connectorsList[i].NextLane.HasFreeOccupation)
            {
                maxInt = randomWeight;
                index = i;
            }
        }

        return connectorsList[index];
    }

    public bool TryToReserve(TSTrafficAI tsTrafficAI, int startingPointIndex, float distance, ref Queue<TSTrafficAI.TSReservedPoints> reservedPoints, bool checkForRoadblocks = true)
    {
        var reservedQty = Mathf.Max(Mathf.RoundToInt(distance / points[1].distanceToNextPoint), 4);
        var index = startingPointIndex + reservedQty;
        
        if (index >= points.Length) { return false; }

        var distanceReserved = 0f;
        var i = startingPointIndex;
        while (distanceReserved <= distance || i < index)
        {
            if (TryToReserve(tsTrafficAI, i) == false)
            {
                UnReservePointsRange(startingPointIndex, i, tsTrafficAI.MyID);
                reservedPoints.Clear();
                return false;
            }

            if (checkForRoadblocks && points[i].roadBlockAhead)
            {
                UnReservePointsRange(startingPointIndex, i, tsTrafficAI.MyID);
                reservedPoints.Clear();
                return false;
            }
            
            if (i > startingPointIndex)
            {
                distanceReserved += points[i].distanceToNextPoint;
            }
            
            reservedPoints.Enqueue(new TSTrafficAI.TSReservedPoints(false, i, points[i]));
            ++i;
        }
        /*
        StringBuilder stringBuilder = new StringBuilder();
        for (var i = startingPointIndex; i < index; i++)
        {
            if (TryToReserve(tsTrafficAI, i) == false)
            {
                UnReservePointsRange(startingPointIndex, i, tsTrafficAI.MyID);
                reservedPoints.Clear();
                return false;
            }

            if (i > startingPointIndex)
            {
                distanceReserved += points[i].distanceToNextPoint;
            }
            stringBuilder.AppendLine($"Point: {i}");
            
            reservedPoints.Enqueue(new TSTrafficAI.TSReservedPoints(false, i, points[i]));
        }
        Debug.Log($"{stringBuilder.ToString()} - {reservedPoints}");
        //Debug.Log(distanceReserved);
        */
        return true;
    }

    private void UnReservePointsRange(int start, int end, int id)
    {
        for (var i = start; i <= Mathf.Min(end, points.Length-1); ++i)
        {
            points[i].TryUnReservePoint(id);
        }
    }
    
    public override bool TryToReserve(TSTrafficAI tsTrafficAI, int pointIndex)
    {
        return pointIndex < points.Length && points[pointIndex].TryReservePoint(tsTrafficAI.MyID, tsTrafficAI);
    }

    public override SwitchResponse TrySwitchToLink(SwitchDirection direction, int pointIndex, int reservationID = 0, int pointsQty = 0, TSTrafficAI carWhoReserves = null, bool travelingReverse = false)
    {
        switch (direction)
        {
            case SwitchDirection.Left:
                if (HasLinkLeft == false)
                {
                    Debug.Log("No lane link found on left");
                    break;
                }

                return new SwitchResponse
                {
                    isContrary = leftLinkData.IsContrary,
                    newBaseInfo = leftLinkData.LinkInfo,
                    newPointIndex = points[pointIndex].leftParallelPointIndex,
                    newPoint = leftLinkData.LinkInfo.Points[points[pointIndex].leftParallelPointIndex]
                };
            case SwitchDirection.Right:
                if (HasLinkRight == false)
                {
                    Debug.Log("No lane link found on right");
                    break;
                }

                return new SwitchResponse()
                {
                    isContrary = rightLinkData.IsContrary,
                    newBaseInfo = rightLinkData.LinkInfo,
                    newPointIndex = points[pointIndex].rightParallelPointIndex,
                    newPoint = rightLinkData.LinkInfo.Points[points[pointIndex].rightParallelPointIndex]
                };
        }

        
        Debug.LogFormat("Failed to switch from lane {0} to {1}", Id, direction);
        
        return new SwitchResponse
        {
            isContrary = false,
            newBaseInfo = this,
            newPointIndex = pointIndex,
            newPoint = points[pointIndex]
        };
    }

    public void AddOccupation(float occupation)
    {
        TotalOccupation += occupation;
    }

    public void DecreaseTotalOccupation(float occupation)
    {
        TotalOccupation -= occupation;
        
        if (TotalOccupation < 0f)
        {
            TotalOccupation = 0f;
        }
    }

    public bool IsConnectedToLane(int nearLane)
    {
        return connectors.Exist(connector => connector.nextLane == nearLane);
    }
}